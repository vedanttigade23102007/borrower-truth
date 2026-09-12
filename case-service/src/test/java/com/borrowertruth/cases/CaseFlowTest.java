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
