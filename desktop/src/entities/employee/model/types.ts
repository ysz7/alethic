export interface Employee {
  id: string;
  name: string;
  title: string;
  description: string;
  tools: string[];
  limits: {
    max_steps: number;
    max_cost_usd: number;
    max_wall_time_seconds: number;
  };
}
