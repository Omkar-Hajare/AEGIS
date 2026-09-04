import http from "k6/http";
import { check, sleep } from "k6";
import { BASE_URL } from "../config.js";

const DEFAULT_PRODUCTS_A = [
  "/data/product/1",
  "/data/product/2",
  "/data/product/3",
];

const DEFAULT_PRODUCTS_B = [
  "/data/product/7",
  "/data/product/8",
  "/data/product/9",
];

function getPaths(value, fallback) {
  return value
    ? value.split(",").map((path) => path.trim())
    : fallback;
}

const PRODUCTS_A = getPaths(
  __ENV.POPULAR_PATHS_A,
  DEFAULT_PRODUCTS_A
);

const PRODUCTS_B = getPaths(
  __ENV.POPULAR_PATHS_B,
  DEFAULT_PRODUCTS_B
);

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
  const products = __ITER % 2 === 0
    ? PRODUCTS_A
    : PRODUCTS_B;

  const product =
    products[Math.floor(Math.random() * products.length)];

  const response = http.get(`${BASE_URL}${product}`, {
    tags: { name: "product_lookup" },
  });

  check(response, {
    "status is 200": (r) => r.status === 200,
  });

  if (SLEEP_SECONDS > 0) {
    sleep(SLEEP_SECONDS);
  }
}
