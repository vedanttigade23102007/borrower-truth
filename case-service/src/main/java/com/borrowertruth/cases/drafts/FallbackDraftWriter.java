package com.borrowertruth.cases.drafts;

import com.borrowertruth.cases.api.Dto.CaseIn;
import com.borrowertruth.cases.api.Dto.FindingIn;
import com.borrowertruth.cases.domain.Playbooks.StepTemplate;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.LocalDate;

/**
 * Fallback chain for drafting: the in-house model service (if configured and
 * healthy) -> the deterministic template. A model failure, timeout or empty reply
 * never blocks a case; the draft records which path produced it.
 */
public class FallbackDraftWriter implements DraftWriter {
    private final String modelUrl;
    private final Duration timeout;
    private final TemplateDraftWriter template;
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();

    public FallbackDraftWriter(String modelUrl, Duration timeout) {
        this(modelUrl, timeout, TemplateDraftWriter.DEFAULT_BANK);
    }

    public FallbackDraftWriter(String modelUrl, Duration timeout, String bank) {
        this.modelUrl = modelUrl == null || modelUrl.isBlank() ? null : modelUrl;
        this.timeout = timeout;
        this.template = new TemplateDraftWriter(bank);
    }

    @Override
    public Draft write(CaseIn c, FindingIn f, StepTemplate step, LocalDate due) {
        Draft base = template.write(c, f, step, due);
        if (modelUrl == null) return base;
        try {
            // The model only rewrites the template's facts into clearer prose; it receives no raw borrower data.
            HttpRequest req = HttpRequest.newBuilder(URI.create(modelUrl + "/rewrite"))
                    .timeout(timeout).header("Content-Type", "text/plain; charset=utf-8")
                    .POST(HttpRequest.BodyPublishers.ofString(base.text())).build();
            HttpResponse<String> res = http.send(req, HttpResponse.BodyHandlers.ofString());
            String body = res.body();
            if (res.statusCode() == 200 && body != null && body.contains("[ref ")) {
                return new Draft(body, "MODEL");
            }
        } catch (Exception ignored) {
            // fall through to the template
        }
        return new Draft(base.text(), "TEMPLATE_FALLBACK");
    }
}
