import http from "k6/http";
import { check, sleep } from "k6";
import { BASE_URL, TARGET_PATH } from "../config.js";

export const options = {
  stages: [
    { duration: "30s", target: 5 },
    { duration: "10s", target: 50 },
    { duration: "60s", target: 50 },
    { duration: "10s", target: 5 },
    { duration: "30s", target: 0 },
  ],
};

export default function () {
  const response = http.get(`${BASE_URL}${TARGET_PATH}`);

  check(response, {
    "status is 200": (r) => r.status === 200,
  });

  sleep(1);
}
