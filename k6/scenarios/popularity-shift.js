import http from "k6/http";
import { check, sleep } from "k6";
import { BASE_URL } from "../config.js";

const DEFAULT_PRODUCTS_A = [
  "/products/1",
  "/products/2",
  "/products/3",
];

const DEFAULT_PRODUCTS_B = [
  "/products/7",
  "/products/8",
  "/products/9",
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
};

export default function () {
  const products = __ITER % 2 === 0
    ? PRODUCTS_A
    : PRODUCTS_B;

  const product =
    products[Math.floor(Math.random() * products.length)];

  const response = http.get(`${BASE_URL}${product}`);

  check(response, {
    "status is 200": (r) => r.status === 200,
  });

  sleep(1);
}
