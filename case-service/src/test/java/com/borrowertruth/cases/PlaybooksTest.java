package com.borrowertruth.cases;

import com.borrowertruth.cases.api.Dto.CaseIn;
import com.borrowertruth.cases.api.Dto.FindingIn;
import com.borrowertruth.cases.api.Dto.SignalIn;
import com.borrowertruth.cases.domain.Playbooks;
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
    void modelDownFallsBackToTemplate() {
        CaseIn c = sampleCase();
        var step = Playbooks.forMechanism("HIDDEN_DEBT").get(0);
        var writer = new FallbackDraftWriter("http://127.0.0.1:9", Duration.ofMillis(300));
        DraftWriter.Draft d = writer.write(c, c.findings().get(0), step, LocalDate.of(2026, 9, 20));
        assertEquals("TEMPLATE_FALLBACK", d.source());
        assertTrue(d.text().contains("[ref "));
    }
}
