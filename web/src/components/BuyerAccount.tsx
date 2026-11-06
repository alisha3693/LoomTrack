import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

/** Who is signed in, with a way to change the password or sign out. Shows nothing for a visitor using a private link. */
export default function BuyerAccount() {
  const { user, signOut } = useAuth();
  const nav = useNavigate();
  if (user?.role !== "buyer") return null;
  return (
    <div className="row no-print" style={{ gap: 8 }}>
      <span className="faint small">{user.name}</span>
      <Link className="btn btn-ghost btn-sm" to="/account/password">Password</Link>
      <button className="btn btn-sm" onClick={() => { signOut(); nav("/", { replace: true }); }}>Sign out</button>
    </div>
  );
}
