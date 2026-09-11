package com.borrowertruth.cases;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

// tests never touch the development database file (a running service holds it open)
@SpringBootTest(properties = "spring.datasource.url=jdbc:h2:mem:contextloads;DB_CLOSE_DELAY=-1")
class CaseServiceApplicationTests {

	@Test
	void contextLoads() {
	}

}
