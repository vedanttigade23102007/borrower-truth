package com.borrowertruth.cases;

import com.borrowertruth.cases.api.Dto.CaseIn;
import com.borrowertruth.cases.api.Dto.FindingIn;
import com.borrowertruth.cases.api.Dto.SignalIn;
import com.borrowertruth.cases.domain.Playbooks;
import com.borrowertruth.cases.service.CaseService;
import com.borrowertruth.cases.drafts.DraftWriter;
import com.borrowertruth.cases.drafts.FallbackDraftWriter;
import com.borrowertruth.cases.drafts.TemplateDraftWriter;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class PlaybooksTest {
    static final List<String> MECHANISMS = List.of("DOUBLE_PLEDGE", "TAPE_DRESSUP", "DISGUISED_RECEIPTS",
            "FAKE_INVOICES", "HIDDEN_DEBT", "RELATED_SHELLS", "FAKE_INVOICES", "FIN_MANIPULATION");

    static CaseIn sampleCase() {
        SignalIn s = new SignalIn("S5-B0001-COMPETING_LIEN-abc", "B0001", "S5", "COMPETING_LIEN", 0.8, 0.85,
                List.of("ucc:TX-UCC-000001"), "'Northgate Capital Partners LLC' holds a lien on the borrower", 11, List.of());
        FindingIn f = new FindingIn("HIDDEN_DEBT", "medium", "the borrower has debt it has not disclosed",
                List.of(s.signalId()), List.of(), List.of("ucc"), List.of("S5"), 11);
        return new CaseIn("B0001", "LIKELY_FRAUD", "Likely: hidden debt", 0.7, List.of(f), List.of(s), List.of(), Map.of("S5", "ok"), null);
    }

    @Test
    void everyDocumentedMechanismHasAPlaybook() {
        for (String m : MECHANISMS) assertFalse(Playbooks.forMechanism(m).isEmpty(), m);
    }

    /** A "worth a look" case: one old lien, filed before onboarding (S5 dates it before month 0). */
    static CaseIn lowCase() {
        SignalIn s = new SignalIn("S5-B0002-COMPETING_LIEN-old", "B0002", "S5", "COMPETING_LIEN", 0.8, 0.5,
                List.of("ucc:TX-UCC-000002"), "'Prairie Capital Partners LLC' holds a lien on the borrower that the borrower "
                + "never disclosed (filed before onboarding: may be a stale filing)", -10, List.of());
        FindingIn f = new FindingIn("HIDDEN_DEBT", "low", "the borrower has debt it has not disclosed",
                List.of(s.signalId()), List.of(), List.of(), List.of("S5"), -10);
        return new CaseIn("B0002", "NEEDS_MORE_EVIDENCE", "Worth a look: hidden debt", 0.32, List.of(f), List.of(s),
                List.of(), Map.of("S5", "ok"), null);
    }

    @Test
    void everyDocumentedMechanismHasOneCheckThatCanClearIt() {
        for (String m : MECHANISMS) {
            var f = new FindingIn(m, "low", "", List.of(), List.of(), List.of(), List.of(), 0);
            var t = Playbooks.checkFor(f, List.of());
            assertNotEquals(Playbooks.EXPLAIN, t, m);  // a specific ask, not the generic fallback
            assertTrue(Playbooks.isCheck(t.code()), t.code());
            assertTrue(Playbooks.forMechanism(m).stream().noneMatch(x -> Playbooks.isCheck(x.code())), m);
        }
        var unknown = new FindingIn("SOMETHING_NEW", "low", "", List.of(), List.of(), List.of(), List.of(), 0);
        assertEquals(Playbooks.EXPLAIN, Playbooks.checkFor(unknown, List.of()));  // never a finding without a step
    }

    @Test
    void anOldLienAsksForItsRelease() {
        CaseIn c = lowCase();
        var t = Playbooks.checkFor(c.findings().get(0), c.signals());
        assertEquals("CHECK_LIEN_RELEASE", t.code());
        DraftWriter.Draft d = new TemplateDraftWriter().write(c, c.findings().get(0), t, LocalDate.of(2026, 10, 11));
        assertTrue(d.text().contains("termination statement (UCC-3)"));
        assertTrue(d.text().contains("[ref S5-B0002-COMPETING_LIEN-old]"));
        assertTrue(d.text().contains("does not allege wrongdoing"));
        // the same lien filed after onboarding is not "old": it gets the general hidden-debt question
        CaseIn recent = PlaybooksTest.sampleCase();
        assertEquals("CHECK_DEBT_EXPLANATION", Playbooks.checkFor(recent.findings().get(0), recent.signals()).code());
    }

    @Test
    void aClueIsWhatItIsAbout() {
        SignalIn lien = lowCase().signals().get(0);
        assertEquals("COMPETING_LIEN|ucc:TX-UCC-000002", Playbooks.clueKey(lien));
        SignalIn payer = new SignalIn("S3-x", "B0002", "S3", "NON_OBLIGOR_PAYER", 0.5, 0.6,
                List.of("payment:T1", "payment:T2", "payer:Summit Property Partners LLC", "total:$774,996 in 2 payments"),
                "", 3, List.of());
        assertEquals("NON_OBLIGOR_PAYER|payer:Summit Property Partners LLC", Playbooks.clueKey(payer));
        SignalIn pattern = new SignalIn("S7-x", "B0002", "S7", "CASH_REVENUE_GAP", 0.6, 0.6,
                List.of("financials:B0002:Q4", "financials:B0002:Q5"), "", 20, List.of());
        assertEquals("CASH_REVENUE_GAP", Playbooks.clueKey(pattern));  // its months change; the clue doesn't
    }

    @Test
    void theLargestDollarAmountInTheClues() {
        assertEquals(774_996L, CaseService.largestAmount(List.of("Judgment of $181,092 against 'Harbor Trade Corp'",
                "$774,996 (1.7% of inflows) came from 'Summit Property Partners LLC'")));
        assertEquals(0L, CaseService.largestAmount(List.of("16.6% of loans reported current had no payment arrive (81 of 488)")));
    }

    @Test
    void lettersCiteEvidenceAndNeverAllege() {
        CaseIn c = sampleCase();
        var step = Playbooks.forMechanism("HIDDEN_DEBT").get(0);
        DraftWriter.Draft d = new TemplateDraftWriter().write(c, c.findings().get(0), step, LocalDate.of(2026, 9, 20));
        assertTrue(d.text().contains("[ref S5-B0001-COMPETING_LIEN-abc]"));
        assertTrue(d.text().contains("Northgate Capital Partners LLC (secured party of record)"));
        assertTrue(d.text().contains("does not allege wrongdoing"));
    }

    @Test
    void lettersAreSignedByTheBankThatRunsIt() {
        CaseIn c = sampleCase();
        var step = Playbooks.forMechanism("HIDDEN_DEBT").get(2);  // a letter to the borrower
        String demo = new TemplateDraftWriter().write(c, c.findings().get(0), step, LocalDate.of(2026, 10, 1)).text();
        String other = new TemplateDraftWriter("First Example Bank").write(c, c.findings().get(0), step, LocalDate.of(2026, 10, 1)).text();
        assertTrue(demo.contains("[Credit officer], Wells Fargo"));  // the worked example stays the default
        assertTrue(other.contains("[Credit officer], First Example Bank"));
        assertFalse(other.contains("Wells Fargo"));
        for (var steps : Playbooks.BY_MECHANISM.values()) {  // no step text names a particular bank
            for (var t : steps) assertFalse(t.ask().contains("WF") || t.ask().contains("Wells Fargo"), t.code());
        }
    }

    @Test
    void modelDownFallsBackToTemplate() {
        CaseIn c = sampleCase();
        var step = Playbooks.forMechanism("HIDDEN_DEBT").get(0);
        var writer = new FallbackDraftWriter("http://127.0.0.1:9", Duration.ofMillis(300));
        DraftWriter.Draft d = writer.write(c, c.findings().get(0), step, LocalDate.of(2026, 9, 20));
        assertEquals("TEMPLATE_FALLBACK", d.source());
        assertTrue(d.text().contains("[ref "));
    }
}
