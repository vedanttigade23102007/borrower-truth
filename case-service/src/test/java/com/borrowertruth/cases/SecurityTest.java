package com.borrowertruth.cases;

import com.borrowertruth.cases.api.Dto.DecisionIn;
import com.borrowertruth.cases.config.WriteGuard;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

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

    @Test
    void oversizedDecisionInputIsRejected() {
        Validator v = Validation.buildDefaultValidatorFactory().getValidator();
        assertTrue(v.validate(new DecisionIn("APPROVE", "officer.a", "fine")).isEmpty());
        assertFalse(v.validate(new DecisionIn("APPROVE", "officer.a", "x".repeat(501))).isEmpty());
        assertFalse(v.validate(new DecisionIn("APPROVE", "u".repeat(81), null)).isEmpty());
    }
}
