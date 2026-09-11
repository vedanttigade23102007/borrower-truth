package com.borrowertruth.cases.domain;

import java.util.List;
import java.util.Map;

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
                "Trace each listed inflow to its originating account, the same money-trail review WF ran by hand after its Q1 2026 loss, now for this case only.", 7),
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
}
