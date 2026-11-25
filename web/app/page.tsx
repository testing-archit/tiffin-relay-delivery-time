import Estimator from "@/components/Estimator";

function Dabba() {
  return (
    <svg width="40" height="44" viewBox="0 0 40 44" aria-hidden="true">
      <rect x="15" y="1" width="10" height="6" rx="2" fill="none" stroke="#1C2830" strokeWidth="2.5" />
      <rect x="5" y="7" width="30" height="7" rx="2" fill="#F2B705" stroke="#1C2830" strokeWidth="2.5" />
      {[15, 25, 35].map(y => <rect key={y} x="6" y={y} width="28" height={y === 35 ? 8 : 9} rx="2" fill="#F4F6F7" stroke="#1C2830" strokeWidth="2.5" />)}
    </svg>
  );
}

export default function Home() {
  return (
    <Estimator
      brand={
        <div className="brand">
          <Dabba />
          <div>
            <h1>Tiffin relay estimator</h1>
            <p>Bhopal Dabba Relay Union. When will lunch reach the desk?</p>
          </div>
        </div>
      }
    />
  );
}
