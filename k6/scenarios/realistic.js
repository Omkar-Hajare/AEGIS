import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8001";
const SLEEP_SECONDS = Number(__ENV.SLEEP_SECONDS || "0.05");

export const options = {
  stages: [
    { duration: "30s", target: 10 },
    { duration: "30s", target: 30 },
    { duration: "30s", target: 50 },
    { duration: "30s", target: 20 },
    { duration: "30s", target: 10 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
  },
};

function randomProductId() {
  if (Math.random() < 0.8) {
    return Math.floor(Math.random() * 10) + 1;
  }

  return Math.floor(Math.random() * 40) + 11;
}

export default function () {
  if (Math.random() < 0.7) {
    const productId = randomProductId();

    const response = http.get(
      `${BASE_URL}/data/product/${productId}`,
      {
        tags: {
          workload: "product",
        },
      }
    );

    check(response, {
      "product status is 200": (r) => r.status === 200,
    });
  } else {
    const userId = Math.floor(Math.random() * 1000) + 1;

    const response = http.get(
      `${BASE_URL}/data/recommendation/${userId}`,
      {
        tags: {
          workload: "recommendation",
        },
      }
    );

    check(response, {
      "recommendation status is 200": (r) => r.status === 200,
    });
  }

  sleep(SLEEP_SECONDS);
}