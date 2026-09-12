package com.borrowertruth.cases.api;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/** Wire formats. The Python pipeline posts {@link RunIn}; the console reads the views. */
public final class Dto {
    private Dto() {}

    public record SignalIn(String signalId, String entityId, String system, String type, double severity,
                           double confidence, List<String> evidence, String explanation, int observedMonth,
                           List<String> relatedEntities) {}

    public record FindingIn(String mechanism, String confidence, String plain, List<String> signals,
                            List<String> corroboratedBy, List<String> sources, List<String> systems, int firstMonth) {}

    public record CaseIn(@NotBlank String borrowerId, @NotBlank String verdict, String headline, double priority,
                         List<FindingIn> findings, List<SignalIn> signals, List<String> explanations,
                         Map<String, String> coverage, Map<String, Object> decision) {}

    public record RunIn(int asOf, Map<String, Object> runMetrics, @NotNull @Valid List<CaseIn> cases) {}

    public record RunAck(int asOf, int cases, int stepsCreated, Instant receivedAt) {}

    public record DecisionIn(@NotBlank String decision, @NotBlank String user, String note) {}

    public record StepView(String mechanism, String code, String title, String kind, String status, String draft,
                           String draftSource, String owner, LocalDate dueDate, String decidedBy, Instant decidedAt,
                           String note) {}

    public record CaseSummary(String borrowerId, String verdict, String headline, double priority,
                              List<String> mechanisms, long openSteps, String caseStatus, int liveAlerts) {}

    public record CaseDetail(CaseIn caseData, List<StepView> steps, List<AuditView> audit, String caseStatus,
                             List<String> unavailableSystems, List<LiveAlertView> liveAlerts) {}

    /** A real-time S3 signal from the streaming worker, forwarded by the signal bridge. */
    public record LiveAlertIn(@NotBlank String borrowerId, @NotBlank String type, String txnId, String payerName,
                              double amount, String entityId, double detectedAt) {}

    public record LiveAlertView(String type, String txnId, String payerName, double amount, Instant detectedAt) {}

    public record AuditView(long id, Instant at, String actor, String borrowerId, String action, String detail) {}

    public record RunStatus(Integer asOf, Instant receivedAt, Map<String, Object> runMetrics, Map<String, Long> verdicts) {}
}
