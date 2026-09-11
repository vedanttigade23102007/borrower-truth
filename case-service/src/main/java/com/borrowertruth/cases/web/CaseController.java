package com.borrowertruth.cases.web;

import com.borrowertruth.cases.api.Dto.*;
import com.borrowertruth.cases.service.CaseService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = {"http://localhost:3000"})
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
