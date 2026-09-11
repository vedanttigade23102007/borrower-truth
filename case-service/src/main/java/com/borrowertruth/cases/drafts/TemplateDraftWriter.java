package com.borrowertruth.cases.drafts;

import com.borrowertruth.cases.api.Dto.CaseIn;
import com.borrowertruth.cases.api.Dto.FindingIn;
import com.borrowertruth.cases.api.Dto.SignalIn;
import com.borrowertruth.cases.domain.Playbooks.Kind;
import com.borrowertruth.cases.domain.Playbooks.StepTemplate;

import java.time.LocalDate;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Deterministic drafts built only from the case's own evidence. This is the last
 * step of the fallback chain (model -> template), so it must always work.
 * Letters request information; they never allege wrongdoing.
 */
public class TemplateDraftWriter implements DraftWriter {
    private static final Pattern QUOTED = Pattern.compile("'([^']+)'");

    @Override
    public Draft write(CaseIn c, FindingIn f, StepTemplate step, LocalDate due) {
        List<SignalIn> evidence = c.signals() == null ? List.of() : c.signals().stream()
                .filter(s -> f.signals() != null && f.signals().contains(s.signalId()))
                .limit(5).toList();
        StringBuilder bullets = new StringBuilder();
        for (SignalIn s : evidence) {
            bullets.append("  - ").append(s.explanation()).append(" [ref ").append(s.signalId()).append("]\n");
        }
        if (step.kind() == Kind.ACTION) {
            return new Draft("""
                    INTERNAL ACTION MEMO — %s
                    Case: %s · Finding: %s (%s confidence)
                    Action: %s
                    Based on:
                    %s
                    Due: %s · Requires approval before it is carried out.
                    [DRAFT — synthetic demonstration data]
                    """.formatted(step.title(), c.borrowerId(), f.plain(), f.confidence(), step.ask(), bullets, due),
                    "TEMPLATE");
        }
        String recipient = recipient(step.recipient(), evidence, c.borrowerId());
        return new Draft("""
                DRAFT LETTER — %s
                To: %s
                Re: Facility monitoring — request for information (%s)

                As part of our routine monitoring of the facility, we have identified items we need to reconcile:
                %s
                Please provide %s by %s.

                This letter requests information to reconcile our records. It does not allege wrongdoing by any party.

                [Credit officer], Wells Fargo
                [DRAFT — requires approval; synthetic demonstration data]
                """.formatted(step.title(), recipient, c.borrowerId(), bullets, step.ask(), due), "TEMPLATE");
    }

    private static String recipient(String role, List<SignalIn> evidence, String borrowerId) {
        if ("OTHER_LENDER".equals(role)) {
            for (SignalIn s : evidence) {
                if (s.type().equals("COMPETING_LIEN") || s.type().equals("UNDISCLOSED_SECURED_PARTY")) {
                    Matcher m = QUOTED.matcher(s.explanation());
                    if (m.find()) return m.group(1) + " (secured party of record)";
                }
            }
            return "[the other secured party of record]";
        }
        if ("DEBTOR".equals(role)) return "[each customer named on the flagged invoices]";
        return "Borrower " + borrowerId + ", attention: Chief Financial Officer";
    }
}
