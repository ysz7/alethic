/** What the model calls on this machine have cost, as the runtime counts it. */
export interface Spend {
  calls: number;
  prompt_tokens: number;
  output_tokens: number;
  cost_usd: number;
}
