import http from "k6/http";
import { check, sleep } from "k6";
import { BASE_URL } from "../config.js";

export const options = {
  stages: [
    { duration: "10s", target: 20 },
    { duration: "10s", target: 50 },
    { duration: "40s", target: 50 },
    { duration: "10s", target: 20 },
    { duration: "10s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
  },
};

const SLEEP_SECONDS =
  __ENV.SLEEP_SECONDS !== undefined
    ? parseFloat(__ENV.SLEEP_SECONDS)
    : 0.01;

export default function () {
  let path;

  if (Math.random() < 0.7) {
    // 70% product traffic
    const productId = `${__VU}-${__ITER}`;
    path = `/data/product/${productId}`;
  } else {
    // 30% recommendation traffic
    const userId = `${__VU}-${__ITER}`;
    path = `/data/recommendation/${userId}`;
  }

  const response = http.get(`${BASE_URL}${path}`, {
    tags: { name: path.split("/").slice(0, 3).join("/") + "/{id}" },
  });

  check(response, {
    "status is 200": (r) => r.status === 200,
  });

  sleep(SLEEP_SECONDS);
}