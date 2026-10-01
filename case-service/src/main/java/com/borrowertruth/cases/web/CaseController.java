package com.borrowertruth.cases.web;

import com.borrowertruth.cases.api.Dto.*;
import com.borrowertruth.cases.service.CaseService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Size;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = {"http://localhost:3000", "http://localhost:3001"})
public class CaseController {
    private final CaseService service;

    public CaseController(CaseService service) {
        this.service = service;
    }

    /** Adapter boundary: the pipeline (or a Kafka consumer) posts each run here. */
    @PostMapping("/runs")
    public RunAck ingest(@Valid @RequestBody RunIn run) {
        return service.ingest(run);
    }

    /** Adapter boundary for streaming: the signal bridge posts batches of real-time S3 alerts here. */
    @PostMapping("/live-alerts")
    public Map<String, Integer> liveAlerts(@RequestBody @Size(max = 5000) List<@Valid LiveAlertIn> alerts) {
        return Map.of("accepted", service.addLive(alerts));
    }

    @GetMapping("/runs/latest")
    public RunStatus latest() {
        return service.status();
    }

    @GetMapping("/cases")
    public List<CaseSummary> cases(@RequestParam(required = false) String verdict) {
        return service.list(verdict);
    }

    @GetMapping("/cases/{borrowerId}")
    public ResponseEntity<CaseDetail> detail(@PathVariable String borrowerId) {
        return ResponseEntity.of(service.detail(borrowerId));
    }

    @PostMapping("/cases/{borrowerId}/steps/{code}/decision")
    public StepView decide(@PathVariable String borrowerId, @PathVariable String code, @Valid @RequestBody DecisionIn in) {
        return service.decide(borrowerId, code, in);
    }

    /** Clears picked for a second person. In a bank only reviewers would see this; that needs the bank's sign-in. */
    @GetMapping("/second-checks")
    public List<SecondCheckView> secondChecks() {
        return service.secondChecks();
    }

    @PostMapping("/second-checks/{borrowerId}/{code}")
    public SecondCheckView review(@PathVariable String borrowerId, @PathVariable String code, @Valid @RequestBody DecisionIn in) {
        return service.review(borrowerId, code, in);
    }

    @GetMapping("/feedback")
    public List<FeedbackRow> feedback() {
        return service.feedback();
    }

    @GetMapping("/audit")
    public List<AuditView> audit() {
        return service.audit(null);
    }

    @ExceptionHandler(NoSuchElementException.class)
    public ResponseEntity<Map<String, String>> notFound(NoSuchElementException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", e.getMessage()));
    }

    @ExceptionHandler({IllegalStateException.class, IllegalArgumentException.class})
    public ResponseEntity<Map<String, String>> conflict(RuntimeException e) {
        return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of("error", e.getMessage()));
    }
}
