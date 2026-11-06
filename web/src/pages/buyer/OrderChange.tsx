import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { useApi } from "../../components/ui";
import ChangeForm from "../../components/ChangeForm";
import BuyerFrame from "./BuyerFrame";

interface View {
  orders: { id: number; poNo: string; style: string; exFactory: string; sizes: { size: string; qty: number }[] }[];
}

export default function OrderChange() {
  const { token = "", orderId } = useParams();
  return <BuyerFrame token={token}>{(_name, today) => <Form token={token} orderId={Number(orderId)} today={today} />}</BuyerFrame>;
}

function Form({ token, orderId, today }: { token: string; orderId: number; today: string }) {
  const nav = useNavigate();
  const { data, error } = useApi<View>(`/api/b/${token}`);
  if (error) return <div className="banner banner-error">{error}</div>;
  if (!data) return <p className="faint">Loading…</p>;
  const order = data.orders.find((o) => o.id === orderId);
  if (!order) return <div className="banner banner-error">We could not find that order.</div>;

  return (
    <div className="stack">
      <div>
        <h2 style={{ fontSize: 22 }}>Ask for a change to {order.poNo}</h2>
        <p className="muted">{order.style}. Tell us the new date, the new quantities, or both. Your merchandiser will confirm, ask a question, or suggest another date. Nothing changes until they accept.</p>
      </div>
      <section className="card card-pad">
        <ChangeForm
          currentDate={order.exFactory}
          currentSizes={order.sizes}
          today={today}
          reasonLabel="Why is the change needed?"
          submitLabel="Send change request"
          onCancel={() => nav(`/b/${token}`)}
          onSubmit={async (body) => {
            const r = await api<{ id: number }>(`/api/b/${token}/orders/${orderId}/amendments`, { body });
            nav(`/b/${token}/requests/${r.id}`);
          }}
        />
      </section>
    </div>
  );
}
