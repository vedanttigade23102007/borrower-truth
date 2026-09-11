package com.borrowertruth.cases.service;

import com.borrowertruth.cases.api.Dto.*;
import com.borrowertruth.cases.domain.Playbooks;
import com.borrowertruth.cases.domain.Playbooks.StepTemplate;
import com.borrowertruth.cases.drafts.DraftWriter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.sql.Timestamp;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/**
 * Cases are recomputed by every pipeline run and held in memory; human decisions
 * (steps, approvals, audit) are durable in the database and survive re-runs.
 */
@Service
public class CaseService {
    public static final Set<String> ACTIONABLE = Set.of("high", "medium");

    private final JdbcTemplate jdbc;
    private final DraftWriter drafts;
    private final MeterRegistry meters;
    private final Clock clock;
    private final Map<String, CaseIn> cases = new ConcurrentHashMap<>();
    private volatile RunIn lastRun;
    private volatile Instant lastRunAt;

    public CaseService(JdbcTemplate jdbc, DraftWriter drafts, MeterRegistry meters, Clock clock) {
        this.jdbc = jdbc;
        this.drafts = drafts;
        this.meters = meters;
        this.clock = clock;
    }

    @Transactional
    public RunAck ingest(RunIn run) {
        int created = 0;
        Map<String, CaseIn> fresh = new HashMap<>();
        for (CaseIn c : run.cases()) {
            fresh.put(c.borrowerId(), c);
            if (c.findings() == null) continue;
            for (FindingIn f : c.findings()) {
                if (!ACTIONABLE.contains(f.confidence())) continue;
                for (StepTemplate t : Playbooks.forMechanism(f.mechanism())) {
                    Integer exists = jdbc.queryForObject(
                            "SELECT count(*) FROM fix_step WHERE borrower_id=? AND mechanism=? AND code=?",
                            Integer.class, c.borrowerId(), f.mechanism(), t.code());
                    if (exists != null && exists > 0) continue;
                    LocalDate due = LocalDate.now(clock).plusDays(t.dueDays());
                    DraftWriter.Draft d = drafts.write(c, f, t, due);
                    jdbc.update("INSERT INTO fix_step (borrower_id, mechanism, code, title, kind, status, draft, draft_source, "
                                    + "owner, due_date, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            c.borrowerId(), f.mechanism(), t.code(), t.title(), t.kind().name(), "PROPOSED",
                            d.text(), d.source(), "credit-officer (unassigned)", due, Timestamp.from(clock.instant()));
                    meters.counter("bt.drafts", "source", d.source()).increment();
                    created++;
                }
            }
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
                        open.getOrDefault(c.borrowerId(), 0L), caseStatus(c.borrowerId())))
                .toList();
    }

    public Optional<CaseDetail> detail(String borrowerId) {
        CaseIn c = cases.get(borrowerId);
        if (c == null) return Optional.empty();
        List<String> down = c.coverage() == null ? List.of() : c.coverage().entrySet().stream()
                .filter(e -> !"ok".equals(e.getValue())).map(Map.Entry::getKey).sorted().toList();
        return Optional.of(new CaseDetail(c, steps(borrowerId), audit(borrowerId), caseStatus(borrowerId), down));
    }

    /** One-click decisions. DONE is only allowed after APPROVE: nothing is carried out unapproved. */
    @Transactional
    public StepView decide(String borrowerId, String code, DecisionIn in) {
        List<StepView> matches = steps(borrowerId).stream().filter(s -> s.code().equals(code)).toList();
        if (matches.isEmpty()) throw new NoSuchElementException("no step " + code + " for " + borrowerId);
        StepView s = matches.get(0);
        String next = switch (in.decision().toUpperCase(Locale.ROOT)) {
            case "APPROVE" -> require(s, "PROPOSED", "APPROVED");
            case "REJECT" -> require(s, "PROPOSED", "REJECTED");
            case "DONE" -> require(s, "APPROVED", "DONE");
            default -> throw new IllegalArgumentException("decision must be APPROVE, REJECT or DONE");
        };
        jdbc.update("UPDATE fix_step SET status=?, decided_by=?, decided_at=?, note=? "
                        + "WHERE borrower_id=? AND mechanism=? AND code=?",
                next, in.user(), Timestamp.from(clock.instant()), in.note(), borrowerId, s.mechanism(), code);
        meters.counter("bt.decisions", "decision", next).increment();
        audit(in.user(), borrowerId, "STEP_" + next, code + (in.note() == null ? "" : " — " + in.note()));
        return steps(borrowerId).stream().filter(x -> x.code().equals(code)).findFirst().orElseThrow();
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

    private static String require(StepView s, String from, String to) {
        if (!from.equals(s.status())) {
            throw new IllegalStateException("step " + s.code() + " is " + s.status() + "; " + to + " needs " + from);
        }
        return to;
    }

    private List<StepView> steps(String borrowerId) {
        return jdbc.query("SELECT mechanism, code, title, kind, status, draft, draft_source, owner, due_date, decided_by, "
                        + "decided_at, note FROM fix_step WHERE borrower_id=? ORDER BY mechanism, created_at, code",
                (rs, i) -> new StepView(rs.getString(1), rs.getString(2), rs.getString(3), rs.getString(4),
                        rs.getString(5), rs.getString(6), rs.getString(7), rs.getString(8),
                        rs.getDate(9) == null ? null : rs.getDate(9).toLocalDate(), rs.getString(10),
                        rs.getTimestamp(11) == null ? null : rs.getTimestamp(11).toInstant(), rs.getString(12)),
                borrowerId);
    }

    private String caseStatus(String borrowerId) {
        List<StepView> st = steps(borrowerId);
        if (st.isEmpty()) return "NO_ACTION";
        if (st.stream().allMatch(s -> s.status().equals("DONE") || s.status().equals("REJECTED"))) return "RESOLVED";
        if (st.stream().anyMatch(s -> s.status().equals("APPROVED") || s.status().equals("DONE"))) return "IN_PROGRESS";
        return "AWAITING_APPROVAL";
    }

    private void audit(String actor, String borrowerId, String action, String detail) {
        jdbc.update("INSERT INTO audit_event (at, actor, borrower_id, action, detail) VALUES (?,?,?,?,?)",
                Timestamp.from(clock.instant()), actor, borrowerId, action, detail);
    }
}
