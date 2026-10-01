package com.borrowertruth.cases;

import com.borrowertruth.cases.api.Dto.*;
import com.borrowertruth.cases.service.CaseService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/** The human-in-the-loop rules, end to end through the real service and database. */
@SpringBootTest(properties = "spring.datasource.url=jdbc:h2:mem:caseflow;DB_CLOSE_DELAY=-1")
class CaseFlowTest {
    @Autowired
    CaseService service;

    @Autowired
    JdbcTemplate jdbc;

    @BeforeEach
    void cleanDatabase() {  // each test starts from an empty book of decisions
        jdbc.update("DELETE FROM fix_step");
        jdbc.update("DELETE FROM audit_event");
    }

    RunIn run() {
        CaseIn c = PlaybooksTest.sampleCase();
        return new RunIn(23, Map.of("total_seconds", 1.0), List.of(c));
    }

    @Test
    void ingestCreatesProposedStepsWithDrafts() {
        RunAck ack = service.ingest(run());
        assertEquals(1, ack.cases());
        CaseDetail d = service.detail("B0001").orElseThrow();
        assertFalse(d.steps().isEmpty());
        assertTrue(d.steps().stream().allMatch(s -> s.status().equals("PROPOSED") && s.draft().contains("[ref ")));
        assertEquals("AWAITING_APPROVAL", d.caseStatus());
    }

    @Test
    void nothingIsDoneBeforeApprovalAndEveryDecisionIsAudited() {
        service.ingest(run());
        String code = service.detail("B0001").orElseThrow().steps().get(0).code();
        assertThrows(IllegalStateException.class, () -> service.decide("B0001", code, new DecisionIn("DONE", "t", null)));
        assertEquals("APPROVED", service.decide("B0001", code, new DecisionIn("APPROVE", "officer.a", "ok")).status());
        assertEquals("DONE", service.decide("B0001", code, new DecisionIn("DONE", "officer.a", null)).status());
        assertThrows(IllegalStateException.class, () -> service.decide("B0001", code, new DecisionIn("REJECT", "t", null)));
        assertTrue(service.audit("B0001").stream().anyMatch(a -> a.action().equals("STEP_DONE") && a.actor().equals("officer.a")));
    }

    @Test
    void feedbackCountsDecisionsPerFindingType() {
        service.ingest(run());
        List<StepView> steps = service.detail("B0001").orElseThrow().steps();
        service.decide("B0001", steps.get(0).code(), new DecisionIn("APPROVE", "officer.a", null));
        service.decide("B0001", steps.get(1).code(), new DecisionIn("REJECT", "officer.a", "already cleared"));
        FeedbackRow f = service.feedback().stream().filter(r -> r.mechanism().equals("HIDDEN_DEBT")).findFirst().orElseThrow();
        assertEquals(1, f.approved());
        assertEquals(1, f.rejected());
        assertEquals(steps.size() - 2, f.proposed());
    }

    RunIn lowRun() {
        return new RunIn(23, Map.of("total_seconds", 1.0), List.of(PlaybooksTest.lowCase()));
    }

    static List<StepView> visible(CaseDetail d) {
        return d.steps().stream().filter(s -> !s.status().equals("STANDBY")).toList();
    }

    @Test
    void worthALookGetsOneCheckAndItsFixStepsWait() {
        RunAck ack = service.ingest(lowRun());
        assertEquals(1, ack.stepsCreated());  // the waiting fix steps are not proposed
        CaseDetail d = service.detail("B0002").orElseThrow();
        assertEquals(List.of("CHECK_LIEN_RELEASE"), visible(d).stream().map(StepView::code).toList());
        assertTrue(visible(d).get(0).check());
        assertEquals(3, d.steps().stream().filter(s -> s.status().equals("STANDBY")).count());
        assertEquals("AWAITING_APPROVAL", d.caseStatus());
        assertEquals(1, service.list(null).get(0).openSteps());
        service.ingest(lowRun());  // a re-run never adds a second check for the same finding
        assertEquals(1, visible(service.detail("B0002").orElseThrow()).size());
    }

    @Test
    void clearingNeedsAReasonAndIsCounted() {
        service.ingest(lowRun());
        assertThrows(IllegalArgumentException.class,
                () -> service.decide("B0002", "CHECK_LIEN_RELEASE", new DecisionIn("CLEAR", "officer.a", " ")));
        StepView s = service.decide("B0002", "CHECK_LIEN_RELEASE",
                new DecisionIn("CLEAR", "officer.a", "UCC-3 on file: Prairie loan repaid in 2024"));
        assertEquals("CLEARED", s.status());
        CaseDetail d = service.detail("B0002").orElseThrow();
        assertEquals("RESOLVED", d.caseStatus());
        assertTrue(d.audit().stream().anyMatch(a -> a.action().equals("STEP_CLEARED") && a.detail().contains("UCC-3 on file")));
        FeedbackRow f = service.feedback().stream().filter(r -> r.mechanism().equals("HIDDEN_DEBT")).findFirst().orElseThrow();
        assertEquals(1, f.cleared());
        assertEquals(0, f.proposed());  // waiting fix steps are not counted as proposed
    }

    @Test
    void escalatingProposesTheFullFix() {
        service.ingest(lowRun());
        service.decide("B0002", "CHECK_LIEN_RELEASE", new DecisionIn("APPROVE", "officer.a", null));
        assertThrows(IllegalArgumentException.class,
                () -> service.decide("B0002", "CHECK_LIEN_RELEASE", new DecisionIn("ESCALATE", "officer.a", null)));
        service.decide("B0002", "CHECK_LIEN_RELEASE", new DecisionIn("ESCALATE", "officer.a", "no release after 10 days"));
        CaseDetail d = service.detail("B0002").orElseThrow();
        assertEquals(4, visible(d).size());
        assertEquals(3, visible(d).stream().filter(s -> s.status().equals("PROPOSED") && !s.check()).count());
        assertEquals("IN_PROGRESS", d.caseStatus());
        assertTrue(d.audit().stream().anyMatch(a -> a.action().equals("FIX_PROPOSED")));
        assertEquals(1, service.feedback().stream().filter(r -> r.mechanism().equals("HIDDEN_DEBT")).findFirst()
                .orElseThrow().escalated());
    }

    @Test
    void checksAndFixesKeepTheirOwnDecisions() {
        service.ingest(run());
        service.ingest(new RunIn(23, Map.of(), List.of(PlaybooksTest.sampleCase(), PlaybooksTest.lowCase())));
        String fix = service.detail("B0001").orElseThrow().steps().get(0).code();
        assertThrows(IllegalArgumentException.class, () -> service.decide("B0001", fix, new DecisionIn("CLEAR", "t", "fine")));
        assertThrows(IllegalArgumentException.class,
                () -> service.decide("B0002", "CHECK_LIEN_RELEASE", new DecisionIn("REJECT", "t", "no")));
        assertThrows(IllegalStateException.class,  // a waiting fix step can't be approved before escalation
                () -> service.decide("B0002", "ESTOPPEL_LETTER", new DecisionIn("APPROVE", "t", null)));
    }

    @Test
    void aFindingThatGrowsBringsItsFixStepsForward() {
        service.ingest(lowRun());
        CaseIn low = PlaybooksTest.lowCase();
        FindingIn medium = new FindingIn("HIDDEN_DEBT", "medium", low.findings().get(0).plain(), low.findings().get(0).signals(),
                List.of(), List.of("ucc", "courts"), List.of("S5"), -10);
        CaseIn grown = new CaseIn("B0002", "LIKELY_FRAUD", "Likely: hidden debt", 0.7, List.of(medium), low.signals(),
                List.of(), low.coverage(), null);
        assertEquals(3, service.ingest(new RunIn(23, Map.of(), List.of(grown))).stepsCreated());
        assertEquals(4, visible(service.detail("B0002").orElseThrow()).size());  // the check stays, the fix arrives
    }

    @Test
    void liveAlertsAttachToTheCaseAndAreCapped() {
        service.ingest(run());
        List<LiveAlertIn> alerts = new java.util.ArrayList<>();
        for (int i = 0; i < 60; i++) {
            alerts.add(new LiveAlertIn("B0001", "RELATED_PARTY_INFLOW", "T" + i, "Apex Customer Collections LLC",
                    1000 + i, "E1", 1.8e9 + i));
        }
        assertEquals(60, service.addLive(alerts));
        CaseDetail d = service.detail("B0001").orElseThrow();
        assertEquals(50, d.liveAlerts().size());
        assertEquals("T59", d.liveAlerts().get(0).txnId());  // newest first
        assertEquals(50, service.list(null).get(0).liveAlerts());
    }
}
