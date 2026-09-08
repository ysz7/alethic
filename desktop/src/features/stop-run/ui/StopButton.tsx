export function StopButton({ onStop }: { onStop: () => void | Promise<void> }) {
  return (
    <button type="button" className="stop" onClick={() => void onStop()}>
      Stop
    </button>
  );
}
