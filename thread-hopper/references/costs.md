# Cost forecasts

Use the same model, speed, unit, and remaining task horizon across strategies. Already-incurred costs are sunk. Estimate each strategy's future work independently; include any extra rediscovery or verification after restart. Check current official rates at https://learn.chatgpt.com/docs/pricing for Codex credits or https://developers.openai.com/api/docs/pricing for API charges. Caching rules: https://developers.openai.com/api/docs/guides/prompt-caching .

For a request with total input I, cached input C, cache writes W, and output O:

`cost = ((I-C-W)*input_rate + C*cached_rate + W*write_rate + O*output_rate)/1_000_000`.

Write tokens are a disjoint part of input, not an additional charge on top of ordinary input. Split write lifetimes into separate buckets when rates differ. Unknown writes or output accounting make the estimate uncertain. Cached tokens still occupy context. Cache hits are observed historical measurements, not guaranteed future hits.

The calculator accepts this structure (illustrative relative rates, not a price list):

```json
{
  "unit": "relative",
  "billing": "relative",
  "rates": {"input": 1, "cached": 0.05, "output": 5},
  "margin": 0.2,
  "cases": [{
    "name": "conservative",
    "strategies": {
      "stay": {"requests": [{"input": 100000, "cached": 100000, "repeat": 5}]},
      "restart": {
        "transition": [{"input": 100000, "cached": 100000, "output": 1000}],
        "requests": [{"input": 10000}, {"input": 10000, "cached": 10000, "repeat": 4}]
      }
    }
  }]
}
```

`billing` is `api`, `codex-credits`, `subscription-proxy`, or `relative`. Supply `unit` honestly, for example USD, credits, or relative. Each case requires stay and restart; optional compact uses the same shape. `transition` records extra handoff/compaction/reconstruction requests; `requests` contains remaining task requests. Requests may have different counts if different workflows need more steps, but must describe the same task outcome. `repeat` defaults to 1. Fields `input`, `cached`, `output` default to zero; input includes cached and write tokens. `writes` is a list of `{ "tokens": 1000, "rate": 1.25 }` with rates per million, in the same unit. Output includes any billed reasoning tokens exactly once.

Use at least a base and a conservative case for recommendations. The calculator only recommends restarting when every supplied case beats the cheapest supplied alternative by at least `margin`. One case is a calculation, not a robust recommendation. Missing compaction forecasts are disclosed. It cannot establish that a forecast is realistic.

For a simplified stationary forecast, `stay=N*S` and `restart=H+F+(N-1)*R`: H is handoff overhead, F first fresh-request cost, R later fresh-request cost, S continuing-request cost. When S>R, restarting is cheaper if `N>(H+F-R)/(S-R)`. Round to the next integer for strict savings. Use explicit forecasts when growth, cache misses, compaction, or model changes invalidate stationarity.

Included subscription limits are not a transparent token invoice. Keep the published credit-rate proxy separate from actual account allowances. No rate-card calculation guarantees latency or output quality. Do not make a transition solely because a cached ratio falls below a fixed percentage.
