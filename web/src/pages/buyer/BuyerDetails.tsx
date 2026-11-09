import { useParams } from "react-router-dom";
import MyDetails from "../../components/MyDetails";
import BuyerFrame from "./BuyerFrame";

/** A signed-in buyer's own name, sign-in email and WhatsApp number. */
export default function BuyerDetails() {
  const { token = "me" } = useParams();
  return (
    <BuyerFrame token={token}>
      {() => (token === "me" ? <MyDetails /> : <p className="muted">Sign in with your own account to change your details.</p>)}
    </BuyerFrame>
  );
}
