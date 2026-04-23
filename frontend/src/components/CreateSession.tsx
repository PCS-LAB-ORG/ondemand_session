interface Props {
  onLaunch: () => void;
  disabled: boolean;
}

export default function CreateSession({ onLaunch, disabled }: Props) {
  return (
    <div className="create-session">
      <button
        className="btn btn-primary"
        onClick={onLaunch}
        disabled={disabled}
      >
        {disabled ? "Launching..." : "Launch New Session"}
      </button>
    </div>
  );
}
