import { Navigate, Outlet, Route, Routes, useParams } from "react-router-dom";
import { useAuth } from "./lib/auth";
import Login from "./pages/Login";
import OfficeShell from "./pages/merch/OfficeShell";
import Board from "./pages/merch/Board";
import OrderNew from "./pages/merch/OrderNew";
import OrderDetail from "./pages/merch/OrderDetail";
import Buyers from "./pages/merch/Buyers";
import Requests from "./pages/merch/Requests";
import RequestDetail from "./pages/merch/RequestDetail";
import Templates from "./pages/merch/Templates";
import TemplateEditor from "./pages/merch/TemplateEditor";
import Units from "./pages/merch/Units";
import SupHome from "./pages/sup/SupHome";
import SupUpdate from "./pages/sup/SupUpdate";
import BuyerView from "./pages/buyer/BuyerView";
import RequestNew from "./pages/buyer/RequestNew";
import BuyerRequest from "./pages/buyer/BuyerRequest";
import OrderChange from "./pages/buyer/OrderChange";
import Landing from "./pages/Landing";
import ChangePassword from "./pages/ChangePassword";

function Home() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Landing />;
  if (user.must_change_secret) return <Navigate to="/account/password" replace />;
  return <Navigate to={user.role === "supervisor" ? "/s" : user.role === "buyer" ? "/b/me" : "/m"} replace />;
}

/** /b/me is the signed-in buyer's own page; any other /b/<token> is a private link and needs no account. */
function BuyerGate() {
  const { token } = useParams();
  const { user, loading } = useAuth();
  if (token !== "me") return <Outlet />;
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "buyer") return <Navigate to="/" replace />;
  if (user.must_change_secret) return <Navigate to="/account/password" replace />;
  return <Outlet />;
}

function RequireRole({ role, children }: { role: "merchandiser" | "supervisor"; children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route
        path="/m"
        element={
          <RequireRole role="merchandiser">
            <OfficeShell />
          </RequireRole>
        }
      >
        <Route index element={<Board />} />
        <Route path="orders/new" element={<OrderNew />} />
        <Route path="orders/:id" element={<OrderDetail />} />
        <Route path="buyers" element={<Buyers />} />
        <Route path="requests" element={<Requests />} />
        <Route path="requests/:id" element={<RequestDetail />} />
        <Route path="units" element={<Units />} />
        <Route path="templates" element={<Templates />} />
        <Route path="templates/new" element={<TemplateEditor />} />
        <Route path="templates/:id" element={<TemplateEditor />} />
      </Route>
      <Route path="/s" element={<RequireRole role="supervisor"><SupHome /></RequireRole>} />
      <Route path="/s/update/:milestoneId" element={<RequireRole role="supervisor"><SupUpdate /></RequireRole>} />
      <Route path="/account/password" element={<ChangePassword />} />
      <Route path="/b/:token" element={<BuyerGate />}>
        <Route index element={<BuyerView />} />
        <Route path="requests/new" element={<RequestNew />} />
        <Route path="orders/:orderId/change" element={<OrderChange />} />
        <Route path="requests/:id" element={<BuyerRequest />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
