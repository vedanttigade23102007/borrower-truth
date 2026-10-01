package com.borrowertruth.cases;

import com.borrowertruth.cases.api.Dto.DecisionIn;
import com.borrowertruth.cases.config.WriteGuard;
import com.borrowertruth.cases.web.CaseController;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;

import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import java.util.regex.Pattern;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.*;

/** Who may write, and how big an input may be. */
class SecurityTest {
    static int status(WriteGuard guard, String method, String addr, String key) throws Exception {
        MockHttpServletRequest req = new MockHttpServletRequest(method, "/api/cases/B0001/steps/S1/decision");
        req.setRemoteAddr(addr);
        if (key != null) req.addHeader("X-BT-Key", key);
        MockHttpServletResponse res = new MockHttpServletResponse();
        guard.doFilter(req, res, new MockFilterChain());
        return res.getStatus();
    }

    @Test
    void writesFromThisMachineOrWithTheKeyOnly() throws Exception {
        WriteGuard guard = new WriteGuard("s3cret");
        assertEquals(200, status(guard, "POST", "127.0.0.1", null));
        assertEquals(200, status(guard, "POST", "::1", null));
        assertEquals(403, status(guard, "POST", "10.0.0.7", null));
        assertEquals(403, status(guard, "POST", "10.0.0.7", "wrong"));
        assertEquals(200, status(guard, "POST", "10.0.0.7", "s3cret"));
        assertEquals(200, status(guard, "GET", "10.0.0.7", null));  // reads stay open
    }

    @Test
    void noKeyConfiguredMeansNoRemoteWrites() throws Exception {
        WriteGuard guard = new WriteGuard("");
        assertEquals(403, status(guard, "POST", "10.0.0.7", ""));
        assertEquals(200, status(guard, "POST", "127.0.0.1", null));
    }

    /**
     * The audit log is append-only in the code: no SQL anywhere in the service changes or removes an audit row, and the
     * API has no PUT, PATCH or DELETE route at all. (In a bank, the database role would also hold INSERT and SELECT
     * only on audit_event; that is deployment configuration, not built here.)
     */
    @Test
    void theAuditLogHasNoUpdateOrDeletePath() throws Exception {
        Pattern change = Pattern.compile("(?is)\\b(update|delete\\s+from|truncate(\\s+table)?|drop\\s+table|alter\\s+table|merge\\s+into)\\s+audit_event\\b");
        List<Path> sources;
        try (Stream<Path> files = Files.walk(Path.of("src/main"))) {
            sources = files.filter(f -> f.toString().endsWith(".java") || f.toString().endsWith(".sql")).toList();
        }
        assertTrue(sources.size() > 10, "found the service sources");
        assertTrue(sources.stream().anyMatch(f -> read(f).contains("INSERT INTO audit_event")), "the log is written somewhere");
        for (Path f : sources) assertFalse(change.matcher(read(f)).find(), f + " changes audit rows");

        for (Method m : CaseController.class.getDeclaredMethods()) {
            assertNull(m.getAnnotation(DeleteMapping.class), m.getName());
            assertNull(m.getAnnotation(PutMapping.class), m.getName());
            assertNull(m.getAnnotation(PatchMapping.class), m.getName());
            RequestMapping r = m.getAnnotation(RequestMapping.class);
            if (r != null) assertTrue(Arrays.stream(r.method()).allMatch(x -> x == RequestMethod.GET || x == RequestMethod.POST), m.getName());
        }
    }

    static String read(Path f) {
        try {
            return Files.readString(f);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    @Test
    void oversizedDecisionInputIsRejected() {
        Validator v = Validation.buildDefaultValidatorFactory().getValidator();
        assertTrue(v.validate(new DecisionIn("APPROVE", "officer.a", "fine")).isEmpty());
        assertFalse(v.validate(new DecisionIn("APPROVE", "officer.a", "x".repeat(501))).isEmpty());
        assertFalse(v.validate(new DecisionIn("APPROVE", "u".repeat(81), null)).isEmpty());
    }
}
