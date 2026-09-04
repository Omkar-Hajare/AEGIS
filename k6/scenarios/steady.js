import http from "k6/http";
import { check, sleep } from "k6";
import { BASE_URL, TARGET_PATH } from "../config.js";

export const options = {
  stages: [
    { duration: "30s", target: 10 },
    { duration: "60s", target: 10 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
  },
};

const SLEEP_SECONDS = __ENV.SLEEP_SECONDS !== undefined ? parseFloat(__ENV.SLEEP_SECONDS) : 1;

export default function () {
  const response = http.get(`${BASE_URL}${TARGET_PATH}`, {
    tags: { name: TARGET_PATH },
  });

  check(response, {
    "status is 200": (r) => r.status === 200,
  });

  if (SLEEP_SECONDS > 0) {
    sleep(SLEEP_SECONDS);
  }
}
