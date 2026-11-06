import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./lib/auth";
import Login from "./pages/Login";
import OfficeShell from "./pages/merch/OfficeShell";
import Board from "./pages/merch/Board";
import OrderNew from "./pages/merch/OrderNew";
import OrderDetail from "./pages/merch/OrderDetail";
import Buyers from "./pages/merch/Buyers";
import Templates from "./pages/merch/Templates";
import TemplateEditor from "./pages/merch/TemplateEditor";
import SupHome from "./pages/sup/SupHome";
import SupUpdate from "./pages/sup/SupUpdate";
import BuyerView from "./pages/buyer/BuyerView";

function Home() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "supervisor" ? "/s" : "/m"} replace />;
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
        <Route path="templates" element={<Templates />} />
        <Route path="templates/new" element={<TemplateEditor />} />
        <Route path="templates/:id" element={<TemplateEditor />} />
      </Route>
      <Route path="/s" element={<RequireRole role="supervisor"><SupHome /></RequireRole>} />
      <Route path="/s/update/:milestoneId" element={<RequireRole role="supervisor"><SupUpdate /></RequireRole>} />
      <Route path="/b/:token" element={<BuyerView />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
