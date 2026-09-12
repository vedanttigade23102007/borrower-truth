package com.borrowertruth.cases.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.net.InetAddress;
import java.net.UnknownHostException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Writes (pipeline runs, live alerts, decisions) are accepted from this machine, or from another machine
 * that sends the shared key in {@code X-BT-Key}. Reads stay open. In a bank deployment officers would sign in
 * through the bank's SSO instead; that is not built.
 */
@Component
public class WriteGuard extends OncePerRequestFilter {
    static final String HEADER = "X-BT-Key";
    private final byte[] key;

    public WriteGuard(@Value("${bt.api-key:}") String key) {
        this.key = key == null ? new byte[0] : key.getBytes(StandardCharsets.UTF_8);
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest req) {
        String m = req.getMethod();
        return !req.getRequestURI().startsWith("/api/") || m.equals("GET") || m.equals("HEAD") || m.equals("OPTIONS");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        if (isLoopback(req.getRemoteAddr()) || keyMatches(req.getHeader(HEADER))) {
            chain.doFilter(req, res);
            return;
        }
        res.setStatus(HttpServletResponse.SC_FORBIDDEN);
        res.setContentType("application/json");
        res.getWriter().write("{\"error\":\"writes from another machine need the " + HEADER + " header\"}");
    }

    static boolean isLoopback(String addr) {
        try {
            return addr != null && InetAddress.getByName(addr).isLoopbackAddress();  // an IP literal: no DNS lookup
        } catch (UnknownHostException e) {
            return false;
        }
    }

    private boolean keyMatches(String given) {
        return key.length > 0 && given != null && MessageDigest.isEqual(key, given.getBytes(StandardCharsets.UTF_8));
    }
}
