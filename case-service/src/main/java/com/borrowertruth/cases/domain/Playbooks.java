package com.borrowertruth.cases.domain;

import com.borrowertruth.cases.api.Dto.FindingIn;
import com.borrowertruth.cases.api.Dto.SignalIn;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * The "suggested fix": one deterministic playbook per documented mechanism
 * (design/SYSTEM-DESIGN.md §5). Steps are proposals; nothing happens until a
 * human approves it.
 */
public final class Playbooks {
    private Playbooks() {}

    public enum Kind { LETTER, ACTION }

    /** A step template. {@code ask} is what a letter requests, or what an action does. */
    public record StepTemplate(String code, String title, Kind kind, String recipient, String ask, int dueDays) {}

    public static final Map<String, List<StepTemplate>> BY_MECHANISM = Map.of(
        "DOUBLE_PLEDGE", List.of(
            new StepTemplate("HOLD_ADVANCES", "Pause new advances against the affected collateral", Kind.ACTION, null,
                "Place a hold on further advances against the collateral named in the evidence until uniqueness is confirmed.", 1),
            new StepTemplate("REQUEST_PAYOFF_LETTER", "Ask the other secured party for a payoff / estoppel letter", Kind.LETTER, "OTHER_LENDER",
                "a payoff or estoppel letter stating the collateral you claim, the amount outstanding, and whether any of it overlaps the listed assets", 5),
            new StepTemplate("RERUN_ELIGIBILITY", "Recompute eligibility without the duplicated assets", Kind.ACTION, null,
                "Recompute the borrowing base excluding every asset that appears in more than one facility.", 3)),
        "TAPE_DRESSUP", List.of(
            new StepTemplate("EXPAND_SAMPLE", "Expand the source-system sample on the affected pool", Kind.ACTION, null,
                "Increase the servicer-system sample to at least 200 loans and compare status field by field.", 3),
            new StepTemplate("FIELD_EXAM", "Schedule a field exam with screen-level source review", Kind.LETTER, "BORROWER",
                "access, within the audit rights of the credit agreement, to the servicing system so our examiners can review the listed loans on screen", 7),
            new StepTemplate("RECOMPUTE_BORROWING_BASE", "Recompute the borrowing base on verified data", Kind.ACTION, null,
                "Recompute availability using verified status only; treat unverified 'current' loans as ineligible.", 5)),
        "DISGUISED_RECEIPTS", List.of(
            new StepTemplate("PAYER_EXPLANATION", "Ask the borrower to explain each non-customer payer", Kind.LETTER, "BORROWER",
                "an explanation and supporting documents for each listed payment, including the relationship between you and each payer", 5),
            new StepTemplate("TRACE_FLOWS", "Trace the flows back to their origin", Kind.ACTION, null,
                "Trace each listed inflow back to the account it came from.", 7),
            new StepTemplate("TIGHTEN_CASH_DOMINION", "Tighten cash dominion on the collection account", Kind.ACTION, null,
                "Require that only obligor or debtor payments are credited to eligible collections; route other inflows to a suspense account.", 5)),
        "FAKE_INVOICES", List.of(
            new StepTemplate("DEBTOR_CONFIRMATIONS", "Send confirmations to the named customers", Kind.LETTER, "DEBTOR",
                "confirmation of whether you owe the listed invoice amounts, and the amounts you have on record", 5),
            new StepTemplate("MARK_INELIGIBLE", "Mark the flagged invoices ineligible pending confirmation", Kind.ACTION, null,
                "Exclude the flagged invoices from the borrowing base until each is confirmed by the named customer.", 1),
            new StepTemplate("WIDEN_CONFIRMATIONS", "Widen confirmations to the same customers' other invoices", Kind.ACTION, null,
                "Extend confirmations to every open invoice for the customers named in the flagged set.", 7)),
        "HIDDEN_DEBT", List.of(
            new StepTemplate("ESTOPPEL_LETTER", "Ask the undisclosed lender for an estoppel letter", Kind.LETTER, "OTHER_LENDER",
                "an estoppel letter stating the amount outstanding, the collateral you hold, and the borrower entities obligated", 5),
            new StepTemplate("INTERCREDITOR_CHECK", "Check the intercreditor position", Kind.ACTION, null,
                "Confirm with legal whether the filing conflicts with the facility's negative pledge and priority.", 5),
            new StepTemplate("UPDATE_DEBT_SCHEDULE", "Require an updated debt schedule and re-test covenants", Kind.LETTER, "BORROWER",
                "a complete schedule of all debt and liens of the company and its affiliates, certified by an officer", 7)),
        "RELATED_SHELLS", List.of(
            new StepTemplate("OWNERSHIP_CERTIFICATION", "Request an ownership certification and related-party schedule", Kind.LETTER, "BORROWER",
                "a certified ownership chart and a schedule of every entity under common ownership or management, with any transactions between them", 7),
            new StepTemplate("ADD_TO_MONITORING", "Add the linked companies to monitoring", Kind.ACTION, null,
                "Add each linked company to lien, court and payment monitoring.", 1)),
        "FIN_MANIPULATION", List.of(
            new StepTemplate("RECONCILIATION_REQUEST", "Request revenue-to-cash reconciliations", Kind.LETTER, "BORROWER",
                "a reconciliation of reported revenue and receivables to cash received, by month, for the listed quarters", 7),
            new StepTemplate("AUDITOR_BRIDGE", "Ask the borrower's auditor to bridge the gap", Kind.ACTION, null,
                "Request that the borrower's auditor explain the difference between reported revenue and verified collections.", 14),
            new StepTemplate("RETEST_COVENANTS", "Re-test covenants on reconciled numbers", Kind.ACTION, null,
                "Recompute covenant metrics on verified figures once reconciliations arrive.", 10))
    );

    public static List<StepTemplate> forMechanism(String mechanism) {
        return BY_MECHANISM.getOrDefault(mechanism, List.of());
    }

    /**
     * "Worth a look" findings (low confidence) get one cheap step that can clear them. The officer then marks
     * the finding Cleared (with a reason) or Escalated, which proposes the mechanism's full playbook above.
     * Without this, a low finding had clues but no next action and no way to record "checked, it's fine".
     */
    public static final String CHECK_PREFIX = "CHECK_";

    public static final StepTemplate LIEN_RELEASE = new StepTemplate("CHECK_LIEN_RELEASE",
            "Ask for the lien release or a payoff letter", Kind.LETTER, "BORROWER",
            "for each listed filing, a copy of its termination statement (UCC-3) or a payoff letter from the secured party "
                    + "showing the debt was repaid, and for any listed judgment, evidence that it has been paid", 10);

    public static final Map<String, StepTemplate> CHECK_BY_MECHANISM = Map.of(
        "DOUBLE_PLEDGE", new StepTemplate("CHECK_COLLATERAL_IDS", "Ask for the identifiers of the listed collateral",
            Kind.LETTER, "BORROWER",
            "the VINs and title documents (or other unique identifiers) for the listed assets, and every facility or trust "
                    + "they have been pledged or sold to", 10),
        "TAPE_DRESSUP", new StepTemplate("CHECK_SERVICER_RECORDS", "Check the listed loans in the servicer system",
            Kind.ACTION, null,
            "Pull the listed loans' payment history from the servicer system and confirm the payments that kept them "
                    + "current, or the written deferment programme that covers them.", 5),
        "DISGUISED_RECEIPTS", new StepTemplate("CHECK_PAYER", "Ask who the listed payer is paying for", Kind.LETTER, "BORROWER",
            "for each listed payer, the customer it paid on behalf of and the arrangement that lets it pay "
                    + "(for example a parent company, an insurer or a factor)", 10),
        "FAKE_INVOICES", new StepTemplate("CHECK_INVOICE_SUPPORT", "Ask for proof of delivery for the listed invoices",
            Kind.LETTER, "BORROWER", "proof of delivery and the customer's purchase order for each listed invoice", 10),
        "HIDDEN_DEBT", new StepTemplate("CHECK_DEBT_EXPLANATION", "Ask the borrower about the listed filing",
            Kind.LETTER, "BORROWER",
            "for each listed filing or judgment, the agreement behind it and the amount outstanding, or evidence that it "
                    + "has been repaid", 10),
        "RELATED_SHELLS", new StepTemplate("CHECK_OWNERSHIP", "Ask how the borrower is connected to the listed companies",
            Kind.LETTER, "BORROWER",
            "an ownership chart showing how you are connected to each listed company, and any payments or contracts "
                    + "between you and them", 10),
        "FIN_MANIPULATION", new StepTemplate("CHECK_WORKINGS", "Ask for the workings behind the listed figures",
            Kind.LETTER, "BORROWER",
            "the covenant calculation and a reconciliation of reported revenue to customer cash received for the listed "
                    + "quarters", 10)
    );

    public static final StepTemplate EXPLAIN = new StepTemplate("CHECK_EXPLAIN", "Ask the borrower to explain the listed items",
            Kind.LETTER, "BORROWER", "an explanation of each listed item, with supporting documents", 10);

    private static final Set<String> LIEN_TYPES = Set.of("COMPETING_LIEN", "UNDISCLOSED_SECURED_PARTY");

    /** The one step that can clear a "worth a look" finding. A lien filed before onboarding (S5 dates it before
     *  month 0) is most often a repaid loan whose filing was never terminated, so the release is what to ask for. */
    public static StepTemplate checkFor(FindingIn finding, List<SignalIn> signals) {
        boolean staleLien = signals != null && finding.signals() != null && signals.stream()
                .anyMatch(s -> finding.signals().contains(s.signalId()) && LIEN_TYPES.contains(s.type()) && s.observedMonth() < 0);
        return staleLien ? LIEN_RELEASE : CHECK_BY_MECHANISM.getOrDefault(finding.mechanism(), EXPLAIN);
    }

    public static boolean isCheck(String code) {
        return code != null && code.startsWith(CHECK_PREFIX);
    }

    /** Evidence that names a thing: a lien filing, a court case, a linked company, a payer, a public trust. */
    private static final List<String> NAMED = List.of("ucc:", "court:", "registry:", "payer:", "public_abs:");

    /**
     * What a clue is about, so a cleared check is asked again only for a new clue. A clue about a named thing is new
     * when the thing is new (a new filing, a new lender, a new payer). A pattern in the borrower's own numbers (a
     * covenant at the edge, revenue ahead of cash) names its months in the evidence, so it would look new every
     * month: it counts as one clue per type.
     */
    public static String clueKey(SignalIn s) {
        String named = s.evidence() == null ? "" : s.evidence().stream()
                .filter(e -> NAMED.stream().anyMatch(e::startsWith)).sorted().collect(Collectors.joining(","));
        return named.isEmpty() ? s.type() : s.type() + "|" + named;
    }
}
