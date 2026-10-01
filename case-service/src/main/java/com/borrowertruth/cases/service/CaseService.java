package com.borrowertruth.cases.service;

import com.borrowertruth.cases.api.Dto.*;
import com.borrowertruth.cases.domain.Playbooks;
import com.borrowertruth.cases.domain.Playbooks.StepTemplate;
import com.borrowertruth.cases.drafts.DraftWriter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.SecureRandom;
import java.sql.Timestamp;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedDeque;
import java.util.function.DoubleSupplier;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Cases are recomputed by every pipeline run and held in memory; human decisions
 * (steps, approvals, audit) are durable in the database and survive re-runs.
 */
@Service
public class CaseService {
    public static final Set<String> ACTIONABLE = Set.of("high", "medium");
    private static final String PROPOSED = "PROPOSED";
    /** A fix step for a "worth a look" finding, waiting unseen until an officer escalates or the evidence grows. */
    private static final String STANDBY = "STANDBY";
    /** An undecided step whose finding is gone from the latest run. Hidden; it comes back if the finding does. */
    private static final String WITHDRAWN = "WITHDRAWN";
    private static final Set<String> CLOSED = Set.of("DONE", "REJECTED", "CLEARED", "ESCALATED");
    private static final Set<String> STARTED = Set.of("APPROVED", "DONE", "CLEARED", "ESCALATED");

    private final JdbcTemplate jdbc;
    private final DraftWriter drafts;
    private final MeterRegistry meters;
    private final Clock clock;
    private final double secondCheckRate;
    private final long largeAmount;
    /** The second-check draw. Unpredictable on purpose; tests replace it. */
    private DoubleSupplier draw = new SecureRandom()::nextDouble;
    private static final Pattern DOLLARS = Pattern.compile("\\$([0-9][0-9,]*)");
    private final Map<String, CaseIn> cases = new ConcurrentHashMap<>();
    private final Map<String, Deque<LiveAlertView>> live = new ConcurrentHashMap<>();
    private static final int LIVE_KEEP = 50;
    private volatile RunIn lastRun;
    private volatile Instant lastRunAt;

    public CaseService(JdbcTemplate jdbc, DraftWriter drafts, MeterRegistry meters, Clock clock,
                       @Value("${bt.second-check.rate:0.10}") double secondCheckRate,
                       @Value("${bt.second-check.large-amount:500000}") long largeAmount) {
        this.jdbc = jdbc;
        this.drafts = drafts;
        this.meters = meters;
        this.clock = clock;
        this.secondCheckRate = secondCheckRate;
        this.largeAmount = largeAmount;
    }

    public void setDraw(DoubleSupplier draw) {  // tests only
        this.draw = draw;
    }

    @Transactional
    public RunAck ingest(RunIn run) {
        int created = 0;
        Map<String, CaseIn> fresh = new HashMap<>();
        for (CaseIn c : run.cases()) {
            fresh.put(c.borrowerId(), c);
            if (c.findings() == null) continue;
            for (FindingIn f : c.findings()) {
                if (ACTIONABLE.contains(f.confidence())) {
                    // also brings forward fix steps that were waiting while this finding was only "worth a look"
                    for (StepTemplate t : Playbooks.forMechanism(f.mechanism())) created += propose(c, f, t, PROPOSED);
                    continue;
                }
                // "worth a look": one step that can clear it; the fix steps wait until an officer escalates
                created += checkNewClues(c, f);
                for (StepTemplate t : Playbooks.forMechanism(f.mechanism())) propose(c, f, t, STANDBY);
            }
            withdrawGone(c, run.asOf());
        }
        cases.clear();
        cases.putAll(fresh);
        lastRun = run;
        lastRunAt = clock.instant();
        audit("pipeline", null, "RUN_INGESTED", "as_of month " + run.asOf() + ", " + run.cases().size()
                + " cases, " + created + " new proposed steps");
        return new RunAck(run.asOf(), run.cases().size(), created, lastRunAt);
    }

    public List<CaseSummary> list(String verdict) {
        Map<String, Long> open = jdbc.query("SELECT borrower_id, count(*) n FROM fix_step "
                        + "WHERE status IN ('PROPOSED','APPROVED') GROUP BY borrower_id",
                rs -> {
                    Map<String, Long> m = new HashMap<>();
                    while (rs.next()) m.put(rs.getString(1), rs.getLong(2));
                    return m;
                });
        return cases.values().stream()
                .filter(c -> verdict == null || verdict.isBlank() || verdict.equalsIgnoreCase(c.verdict()))
                .sorted(Comparator.comparingDouble(CaseIn::priority).reversed())
                .map(c -> new CaseSummary(c.borrowerId(), c.verdict(), c.headline(), c.priority(),
                        c.findings() == null ? List.of() : c.findings().stream()
                                .filter(f -> ACTIONABLE.contains(f.confidence())).map(FindingIn::mechanism).toList(),
                        open.getOrDefault(c.borrowerId(), 0L), caseStatus(c.borrowerId()),
                        live.getOrDefault(c.borrowerId(), new ArrayDeque<>()).size()))
                .toList();
    }

    /** Real-time alerts from the streaming worker. Kept in memory (the newest 50 per borrower); each batch is audited. */
    public int addLive(List<LiveAlertIn> alerts) {
        Map<String, Integer> perBorrower = new TreeMap<>();
        for (LiveAlertIn a : alerts) {
            Deque<LiveAlertView> q = live.computeIfAbsent(a.borrowerId(), k -> new ConcurrentLinkedDeque<>());
            q.addFirst(new LiveAlertView(a.type(), a.txnId(), a.payerName(), a.amount(),
                    Instant.ofEpochMilli((long) (a.detectedAt() * 1000))));
            while (q.size() > LIVE_KEEP) q.pollLast();
            perBorrower.merge(a.borrowerId(), 1, Integer::sum);
        }
        perBorrower.forEach((b, n) -> audit("stream", b, "LIVE_ALERT", n + " real-time payment alert(s) from S3"));
        meters.counter("bt.live_alerts").increment(alerts.size());
        return alerts.size();
    }

    public Optional<CaseDetail> detail(String borrowerId) {
        CaseIn c = cases.get(borrowerId);
        if (c == null) return Optional.empty();
        List<String> down = c.coverage() == null ? List.of() : c.coverage().entrySet().stream()
                .filter(e -> e.getValue() == null || !e.getValue().startsWith("ok"))  // "ok (495 documents read)" is ok
                .map(e -> e.getKey() + ": " + e.getValue()).sorted().toList();
        return Optional.of(new CaseDetail(c, steps(borrowerId), audit(borrowerId), caseStatus(borrowerId), down,
                List.copyOf(live.getOrDefault(borrowerId, new ArrayDeque<>()))));
    }

    /**
     * One-click decisions. DONE is only allowed after APPROVE: nothing is carried out unapproved. Every decision needs
     * the officer's own name, and a letter (anything that leaves the bank) needs a second person to mark it done.
     * A "worth a look" check ends in CLEAR or ESCALATE, and both need a reason: "checked, it's fine, because …"
     * is what an auditor and the rules owner read later. ESCALATE proposes the finding's full fix steps.
     */
    @Transactional
    public StepView decide(String borrowerId, String code, DecisionIn in) {
        List<StepView> matches = steps(borrowerId).stream().filter(s -> s.code().equals(code)).toList();
        if (matches.isEmpty()) throw new NoSuchElementException("no step " + code + " for " + borrowerId);
        StepView s = matches.get(0);
        String user = realName(in.user());
        String decision = in.decision().toUpperCase(Locale.ROOT);
        String next = switch (decision) {
            case "APPROVE" -> require(s, "APPROVED", PROPOSED);
            case "REJECT" -> require(fixOnly(s, decision), "REJECTED", PROPOSED);
            case "DONE" -> require(secondPerson(fixOnly(s, decision), user), "DONE", "APPROVED");
            case "CLEAR" -> require(withReason(checkOnly(s, decision), in), "CLEARED", PROPOSED, "APPROVED");
            case "ESCALATE" -> require(withReason(checkOnly(s, decision), in), "ESCALATED", PROPOSED, "APPROVED");
            default -> throw new IllegalArgumentException("decision must be APPROVE, REJECT, DONE, CLEAR or ESCALATE");
        };
        jdbc.update("UPDATE fix_step SET status=?, decided_by=?, decided_at=?, note=? "
                        + "WHERE borrower_id=? AND mechanism=? AND code=?",
                next, user, Timestamp.from(clock.instant()), in.note(), borrowerId, s.mechanism(), code);
        if (next.equals("APPROVED")) {  // kept on the step after later decisions: "who approved this letter?"
            jdbc.update("UPDATE fix_step SET approved_by=? WHERE borrower_id=? AND mechanism=? AND code=?",
                    user, borrowerId, s.mechanism(), code);
        }
        meters.counter("bt.decisions", "decision", next).increment();
        audit(user, borrowerId, "STEP_" + next, code + (in.note() == null ? "" : " — " + in.note()));
        if (next.equals("ESCALATED")) proposeFix(borrowerId, s.mechanism(), user);
        if (next.equals("CLEARED")) pickForSecondCheck(borrowerId, s, user);  // after the clear, never before
        return steps(borrowerId).stream().filter(x -> x.code().equals(code)).findFirst().orElseThrow();
    }

    /** An escalated finding gets its full fix: the waiting steps become PROPOSED, drafted from today's evidence. */
    private void proposeFix(String borrowerId, String mechanism, String user) {
        CaseIn c = cases.get(borrowerId);
        FindingIn f = c == null || c.findings() == null ? null
                : c.findings().stream().filter(x -> x.mechanism().equals(mechanism)).findFirst().orElse(null);
        int n = 0;
        for (StepTemplate t : Playbooks.forMechanism(mechanism)) n += promote(borrowerId, c, f, mechanism, t);
        audit(user, borrowerId, "FIX_PROPOSED", mechanism + ": " + n + " fix step(s) proposed after escalation");
    }

    /**
     * A second person checks a sample of clears (Vedant, 1 Oct 2026): every clear whose clues name a large amount
     * ($500,000 or more by default, set from the dev books), and a random 1 in 10 of the rest. The draw happens after
     * the clear, and nothing on the officer's case screens shows it: the pick goes to the second-check list and to
     * the bank-wide audit log, not to the case's own log.
     */
    private void pickForSecondCheck(String borrowerId, StepView s, String clearedBy) {
        long amount = largestAmount(clueTexts(borrowerId, s));
        String reason = amount >= largeAmount ? "LARGE_AMOUNT" : draw.getAsDouble() < secondCheckRate ? "RANDOM" : null;
        if (reason == null) return;
        jdbc.update("INSERT INTO second_check (borrower_id, mechanism, code, reason, amount, cleared_by, picked_at, status) "
                        + "VALUES (?,?,?,?,?,?,?,?)", borrowerId, s.mechanism(), s.code(), reason, amount > 0 ? amount : null,
                clearedBy, Timestamp.from(clock.instant()), "WAITING");
        meters.counter("bt.second_checks", "reason", reason).increment();
        audit("second-check", null, "SECOND_CHECK_PICKED", borrowerId + " " + s.code() + " (" + reason.toLowerCase(Locale.ROOT) + ")");
    }

    /** What the cleared check asked about: its clues' own words, or its letter if the case isn't in memory. */
    private List<String> clueTexts(String borrowerId, StepView s) {
        String clues = jdbc.queryForObject("SELECT clues FROM fix_step WHERE borrower_id=? AND mechanism=? AND code=?",
                String.class, borrowerId, s.mechanism(), s.code());
        Set<String> keys = clues == null ? Set.of() : new HashSet<>(Arrays.asList(clues.split("\n")));
        CaseIn c = cases.get(borrowerId);
        List<String> texts = new ArrayList<>();
        if (c != null && c.signals() != null) {
            for (SignalIn x : c.signals()) if (keys.contains(Playbooks.clueKey(x))) texts.add(x.explanation());
        }
        if (texts.isEmpty() && s.draft() != null) texts.add(s.draft());
        return texts;
    }

    /** The largest dollar amount in the texts ("$774,996 (1.7% of inflows) came from …"), or 0. */
    public static long largestAmount(List<String> texts) {
        long max = 0;
        for (String t : texts) {
            if (t == null) continue;
            Matcher m = DOLLARS.matcher(t);
            while (m.find()) max = Math.max(max, Long.parseLong(m.group(1).replace(",", "")));
        }
        return max;
    }

    /** The second-check list, newest first. In a bank only reviewers would see it; that needs the bank's sign-in. */
    public List<SecondCheckView> secondChecks() {
        return jdbc.query("SELECT sc.borrower_id, sc.mechanism, sc.code, f.title, sc.reason, sc.amount, sc.cleared_by, f.note, "
                        + "sc.picked_at, sc.status, sc.reviewer, sc.reviewed_at, sc.note FROM second_check sc JOIN fix_step f "
                        + "ON f.borrower_id=sc.borrower_id AND f.mechanism=sc.mechanism AND f.code=sc.code "
                        + "ORDER BY sc.picked_at DESC, sc.borrower_id",
                (rs, i) -> new SecondCheckView(rs.getString(1), rs.getString(2), rs.getString(3), rs.getString(4),
                        rs.getString(5), rs.getObject(6) == null ? null : rs.getLong(6), rs.getString(7), rs.getString(8),
                        rs.getTimestamp(9).toInstant(), rs.getString(10), rs.getString(11),
                        rs.getTimestamp(12) == null ? null : rs.getTimestamp(12).toInstant(), rs.getString(13)));
    }

    /**
     * The second person agrees with the clear, or disagrees, which escalates the finding to its full fix. The officer
     * who cleared it can't be its second check, and a disagreement needs a reason.
     */
    @Transactional
    public SecondCheckView review(String borrowerId, String code, DecisionIn in) {
        String user = realName(in.user());
        SecondCheckView sc = secondChecks().stream().filter(x -> x.borrowerId().equals(borrowerId) && x.code().equals(code))
                .findFirst().orElseThrow(() -> new NoSuchElementException("no second check for " + code + " of " + borrowerId));
        if (!sc.status().equals("WAITING")) throw new IllegalStateException("this second check is already " + sc.status());
        if (sc.clearedBy().trim().equalsIgnoreCase(user)) {
            throw new IllegalStateException(sc.clearedBy() + " cleared this, so someone else must be its second check");
        }
        String decision = in.decision().toUpperCase(Locale.ROOT);
        String next = switch (decision) {
            case "AGREE" -> "AGREED";
            case "DISAGREE" -> {
                if (in.note() == null || in.note().isBlank()) throw new IllegalArgumentException("DISAGREE needs a reason in the note");
                yield "DISAGREED";
            }
            default -> throw new IllegalArgumentException("decision must be AGREE or DISAGREE");
        };
        Timestamp now = Timestamp.from(clock.instant());
        jdbc.update("UPDATE second_check SET status=?, reviewer=?, reviewed_at=?, note=? WHERE borrower_id=? AND mechanism=? "
                + "AND code=?", next, user, now, in.note(), borrowerId, sc.mechanism(), code);
        meters.counter("bt.second_checks_reviewed", "outcome", next).increment();
        audit(user, borrowerId, "SECOND_CHECK_" + next, code + (in.note() == null ? "" : " — " + in.note()));
        if (next.equals("DISAGREED")) {
            jdbc.update("UPDATE fix_step SET status='ESCALATED', decided_by=?, decided_at=?, note=? WHERE borrower_id=? "
                    + "AND mechanism=? AND code=?", user, now, "second check disagreed: " + in.note(), borrowerId, sc.mechanism(), code);
            proposeFix(borrowerId, sc.mechanism(), user);
        }
        return secondChecks().stream().filter(x -> x.borrowerId().equals(borrowerId) && x.code().equals(code)).findFirst().orElseThrow();
    }

    /**
     * The learning loop, kept human: officers' approvals and rejections per finding type. A type whose fixes are
     * rejected often goes to the rules owner for review. Rules never change themselves; that would be an
     * unvalidated model change.
     */
    public List<FeedbackRow> feedback() {
        return jdbc.query("SELECT mechanism, "
                        + "SUM(CASE WHEN status='PROPOSED' THEN 1 ELSE 0 END), SUM(CASE WHEN status='APPROVED' THEN 1 ELSE 0 END), "
                        + "SUM(CASE WHEN status='REJECTED' THEN 1 ELSE 0 END), SUM(CASE WHEN status='DONE' THEN 1 ELSE 0 END), "
                        + "SUM(CASE WHEN status='CLEARED' THEN 1 ELSE 0 END), SUM(CASE WHEN status='ESCALATED' THEN 1 ELSE 0 END) "
                        + "FROM fix_step WHERE status NOT IN ('STANDBY','WITHDRAWN') GROUP BY mechanism ORDER BY mechanism",
                (rs, i) -> new FeedbackRow(rs.getString(1), rs.getLong(2), rs.getLong(3), rs.getLong(4), rs.getLong(5),
                        rs.getLong(6), rs.getLong(7)));
    }

    public RunStatus status() {
        Map<String, Long> verdicts = cases.values().stream()
                .collect(Collectors.groupingBy(CaseIn::verdict, TreeMap::new, Collectors.counting()));
        return new RunStatus(lastRun == null ? null : lastRun.asOf(), lastRunAt,
                lastRun == null ? Map.of() : lastRun.runMetrics(), verdicts);
    }

    public List<AuditView> audit(String borrowerId) {
        String sql = "SELECT id, at, actor, borrower_id, action, detail FROM audit_event "
                + (borrowerId == null ? "" : "WHERE borrower_id = ? ") + "ORDER BY id DESC LIMIT 200";
        Object[] args = borrowerId == null ? new Object[0] : new Object[]{borrowerId};
        return jdbc.query(sql, (rs, i) -> new AuditView(rs.getLong(1), rs.getTimestamp(2).toInstant(), rs.getString(3),
                rs.getString(4), rs.getString(5), rs.getString(6)), args);
    }

    private static String require(StepView s, String to, String... from) {
        if (!Arrays.asList(from).contains(s.status())) {
            throw new IllegalStateException("step " + s.code() + " is " + s.status() + "; " + to + " needs "
                    + String.join(" or ", from));
        }
        return to;
    }

    private static String realName(String name) {
        String user = name == null ? "" : name.trim();
        if (user.isEmpty() || user.equalsIgnoreCase("unknown")) {
            throw new IllegalArgumentException("a decision needs the officer's own name, not '" + user + "'");
        }
        return user;
    }

    private static StepView fixOnly(StepView s, String decision) {
        if (s.check()) throw new IllegalArgumentException(s.code() + " is a check: it ends in CLEAR or ESCALATE, not " + decision);
        return s;
    }

    /** Four eyes: whoever approved a letter can't also confirm it was sent. Internal actions don't need this. */
    private static StepView secondPerson(StepView s, String user) {
        String approver = s.approvedBy() != null ? s.approvedBy() : s.status().equals("APPROVED") ? s.decidedBy() : null;
        if ("LETTER".equals(s.kind()) && approver != null && approver.trim().equalsIgnoreCase(user)) {
            throw new IllegalStateException("four eyes: " + approver + " approved this letter, so someone else must mark it done");
        }
        return s;
    }

    private static StepView checkOnly(StepView s, String decision) {
        if (!s.check()) throw new IllegalArgumentException(decision + " applies to a 'worth a look' check, not to fix step " + s.code());
        return s;
    }

    private static StepView withReason(StepView s, DecisionIn in) {
        if (in.note() == null || in.note().isBlank()) {
            throw new IllegalArgumentException(in.decision().toUpperCase(Locale.ROOT) + " needs a reason in the note");
        }
        return s;
    }

    /**
     * Undecided steps whose finding is gone from this run (the evidence changed, or an optional module was turned off)
     * are withdrawn, so nobody works on a finding that no longer exists. Steps already approved or decided stay.
     */
    private void withdrawGone(CaseIn c, int asOf) {
        Set<String> present = c.findings() == null ? Set.of()
                : c.findings().stream().map(FindingIn::mechanism).collect(Collectors.toSet());
        for (Map<String, Object> r : jdbc.queryForList("SELECT mechanism, SUM(CASE WHEN status='PROPOSED' THEN 1 ELSE 0 END) n "
                + "FROM fix_step WHERE borrower_id=? AND status IN ('PROPOSED','STANDBY') GROUP BY mechanism", c.borrowerId())) {
            String m = (String) r.get("mechanism");
            if (present.contains(m)) continue;
            jdbc.update("UPDATE fix_step SET status=?, decided_by='pipeline', decided_at=?, note=? WHERE borrower_id=? "
                            + "AND mechanism=? AND status IN ('PROPOSED','STANDBY')", WITHDRAWN, Timestamp.from(clock.instant()),
                    "the finding is no longer present (run as of month " + (asOf + 1) + ")", c.borrowerId(), m);
            long n = ((Number) r.get("n")).longValue();
            if (n > 0) audit("pipeline", c.borrowerId(), "STEP_WITHDRAWN", m + ": " + n + " undecided step(s); the finding is no longer present");
        }
    }

    /** Creates a step in the given status, or brings a waiting or withdrawn step back. Returns 1 if a step was proposed. */
    private int propose(CaseIn c, FindingIn f, StepTemplate t, String status) {
        List<String> current = jdbc.queryForList("SELECT status FROM fix_step WHERE borrower_id=? AND mechanism=? AND code=?",
                String.class, c.borrowerId(), f.mechanism(), t.code());
        if (!current.isEmpty()) {
            String now = current.get(0);
            if (PROPOSED.equals(status) && (now.equals(STANDBY) || now.equals(WITHDRAWN))) {
                return promote(c.borrowerId(), c, f, f.mechanism(), t);
            }
            if (STANDBY.equals(status) && now.equals(WITHDRAWN)) {  // the finding is back, still only "worth a look"
                jdbc.update("UPDATE fix_step SET status=?, decided_by=NULL, decided_at=NULL, note=NULL WHERE borrower_id=? "
                        + "AND mechanism=? AND code=?", STANDBY, c.borrowerId(), f.mechanism(), t.code());
            }
            return 0;
        }
        insert(c, f, t, status, null);
        return PROPOSED.equals(status) ? 1 : 0;
    }

    /**
     * A "worth a look" finding gets a check for every clue no check has asked about yet: the first time, all of them;
     * after that, only a new clue (a new filing, a new lender), never the same one again. Returns 1 if a check was proposed.
     */
    private int checkNewClues(CaseIn c, FindingIn f) {
        Map<String, String> clueOf = new LinkedHashMap<>();  // this finding's signal id -> what the clue is about
        for (SignalIn s : c.signals() == null ? List.<SignalIn>of() : c.signals()) {
            if (f.signals() != null && f.signals().contains(s.signalId())) clueOf.put(s.signalId(), Playbooks.clueKey(s));
        }
        // codes are unique per borrower, so a decision's (borrower, code) names one step: an old lien can sit under
        // two kinds of finding, and both would otherwise be CHECK_LIEN_RELEASE
        List<Map<String, Object>> rows = jdbc.queryForList("SELECT code, clues, mechanism, status FROM fix_step WHERE borrower_id=?",
                c.borrowerId());
        Set<String> codes = new HashSet<>();
        Set<String> asked = new HashSet<>();
        boolean anyCheck = false;
        String reopen = null;  // a check withdrawn before anyone answered it: asked again under its own code
        for (Map<String, Object> r : rows) {
            String code = (String) r.get("code");
            codes.add(code);
            if (!Playbooks.isCheck(code) || !f.mechanism().equals(r.get("mechanism"))) continue;
            if (WITHDRAWN.equals(r.get("status"))) {
                if (reopen == null) reopen = code;
                continue;
            }
            anyCheck = true;
            String clues = (String) r.get("clues");
            if (clues == null) {  // a check made before clues were tracked (1 Oct 2026) covers what the finding holds now
                clues = String.join("\n", new LinkedHashSet<>(clueOf.values()));
                jdbc.update("UPDATE fix_step SET clues=? WHERE borrower_id=? AND mechanism=? AND code=?",
                        clues, c.borrowerId(), f.mechanism(), code);
            }
            asked.addAll(Arrays.asList(clues.split("\n")));
        }
        List<String> fresh = clueOf.entrySet().stream().filter(e -> !asked.contains(e.getValue())).map(Map.Entry::getKey).toList();
        if (anyCheck && fresh.isEmpty()) return 0;
        // the letter is about the new clues only
        FindingIn about = fresh.isEmpty() ? f : new FindingIn(f.mechanism(), f.confidence(), f.plain(), fresh,
                f.corroboratedBy(), f.sources(), f.systems(), f.firstMonth());
        StepTemplate t = Playbooks.checkFor(about, c.signals());
        String clues = String.join("\n", fresh.stream().map(clueOf::get).collect(Collectors.toCollection(LinkedHashSet::new)));
        if (reopen != null) {
            StepTemplate named = new StepTemplate(reopen, t.title(), t.kind(), t.recipient(), t.ask(), t.dueDays());
            LocalDate due = LocalDate.now(clock).plusDays(t.dueDays());
            DraftWriter.Draft d = drafts.write(c, about, named, due);
            jdbc.update("UPDATE fix_step SET status=?, title=?, kind=?, draft=?, draft_source=?, due_date=?, clues=?, "
                            + "decided_by=NULL, decided_at=NULL, note=NULL WHERE borrower_id=? AND mechanism=? AND code=?",
                    PROPOSED, t.title(), t.kind().name(), d.text(), d.source(), due, clues, c.borrowerId(), f.mechanism(), reopen);
            return 1;
        }
        String code = t.code();
        for (int n = 2; codes.contains(code); n++) code = t.code() + "-" + n;  // e.g. asked again: CHECK_LIEN_RELEASE-2
        insert(c, about, new StepTemplate(code, t.title(), t.kind(), t.recipient(), t.ask(), t.dueDays()), PROPOSED, clues);
        return 1;
    }

    private void insert(CaseIn c, FindingIn f, StepTemplate t, String status, String clues) {
        LocalDate due = LocalDate.now(clock).plusDays(t.dueDays());
        DraftWriter.Draft d = drafts.write(c, f, t, due);
        jdbc.update("INSERT INTO fix_step (borrower_id, mechanism, code, title, kind, status, draft, draft_source, "
                        + "owner, due_date, created_at, clues) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                c.borrowerId(), f.mechanism(), t.code(), t.title(), t.kind().name(), status,
                d.text(), d.source(), "credit-officer (unassigned)", due, Timestamp.from(clock.instant()), clues);
        meters.counter("bt.drafts", "source", d.source()).increment();
    }

    /** A waiting fix step becomes PROPOSED, with a fresh due date and a draft written from today's evidence. */
    private int promote(String borrowerId, CaseIn c, FindingIn f, String mechanism, StepTemplate t) {
        LocalDate due = LocalDate.now(clock).plusDays(t.dueDays());
        if (c == null || f == null) {  // the case isn't in this run's memory: keep the stored draft
            return jdbc.update("UPDATE fix_step SET status=?, due_date=?, decided_by=NULL, decided_at=NULL, note=NULL "
                    + "WHERE borrower_id=? AND mechanism=? AND code=? AND status IN (?,?)", PROPOSED, due, borrowerId,
                    mechanism, t.code(), STANDBY, WITHDRAWN);
        }
        DraftWriter.Draft d = drafts.write(c, f, t, due);
        int n = jdbc.update("UPDATE fix_step SET status=?, due_date=?, draft=?, draft_source=?, decided_by=NULL, "
                + "decided_at=NULL, note=NULL WHERE borrower_id=? AND mechanism=? AND code=? AND status IN (?,?)", PROPOSED,
                due, d.text(), d.source(), borrowerId, mechanism, t.code(), STANDBY, WITHDRAWN);
        if (n > 0) meters.counter("bt.drafts", "source", d.source()).increment();
        return n;
    }

    private List<StepView> steps(String borrowerId) {
        return jdbc.query("SELECT mechanism, code, title, kind, status, draft, draft_source, owner, due_date, decided_by, "
                        + "decided_at, note, approved_by FROM fix_step WHERE borrower_id=? ORDER BY mechanism, created_at, code",
                (rs, i) -> new StepView(rs.getString(1), rs.getString(2), rs.getString(3), rs.getString(4),
                        rs.getString(5), rs.getString(6), rs.getString(7), rs.getString(8),
                        rs.getDate(9) == null ? null : rs.getDate(9).toLocalDate(), rs.getString(10),
                        rs.getTimestamp(11) == null ? null : rs.getTimestamp(11).toInstant(), rs.getString(12),
                        Playbooks.isCheck(rs.getString(2)), rs.getString(13)),
                borrowerId);
    }

    private String caseStatus(String borrowerId) {
        List<StepView> st = steps(borrowerId).stream().filter(s -> !s.status().equals(STANDBY) && !s.status().equals(WITHDRAWN)).toList();
        if (st.isEmpty()) return "NO_ACTION";
        if (st.stream().allMatch(s -> CLOSED.contains(s.status()))) return "RESOLVED";
        if (st.stream().anyMatch(s -> STARTED.contains(s.status()))) return "IN_PROGRESS";
        return "AWAITING_APPROVAL";
    }

    private void audit(String actor, String borrowerId, String action, String detail) {
        jdbc.update("INSERT INTO audit_event (at, actor, borrower_id, action, detail) VALUES (?,?,?,?,?)",
                Timestamp.from(clock.instant()), actor, borrowerId, action, detail);
    }
}
