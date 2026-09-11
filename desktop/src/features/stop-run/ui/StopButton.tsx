import { StopIcon } from "../../../shared/ui";

export function StopButton({ onStop }: { onStop: () => void | Promise<void> }) {
  return (
    <button type="button" className="mini bordered stop" onClick={() => void onStop()}>
      <StopIcon />
      Stop
    </button>
  );
}
