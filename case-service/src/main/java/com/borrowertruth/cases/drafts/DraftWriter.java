package com.borrowertruth.cases.drafts;

import com.borrowertruth.cases.api.Dto.CaseIn;
import com.borrowertruth.cases.api.Dto.FindingIn;
import com.borrowertruth.cases.domain.Playbooks.StepTemplate;

import java.time.LocalDate;

/** Writes the paperwork for one proposed step. Implementations must never send anything. */
public interface DraftWriter {
    record Draft(String text, String source) {}

    Draft write(CaseIn c, FindingIn finding, StepTemplate step, LocalDate due);
}
