package com.borrowertruth.cases.config;

import com.borrowertruth.cases.drafts.DraftWriter;
import com.borrowertruth.cases.drafts.FallbackDraftWriter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;
import java.time.Duration;

@Configuration
public class AppConfig {
    @Bean
    Clock clock() {
        return Clock.systemUTC();
    }

    /** bt.model-url empty => template drafts only (the always-available fallback). Letters are signed by bt.bank-name. */
    @Bean
    DraftWriter draftWriter(@Value("${bt.model-url:}") String modelUrl,
                            @Value("${bt.model-timeout-seconds:8}") long timeoutSeconds,
                            @Value("${bt.bank-name:Wells Fargo}") String bankName) {
        return new FallbackDraftWriter(modelUrl, Duration.ofSeconds(timeoutSeconds), bankName);
    }
}
