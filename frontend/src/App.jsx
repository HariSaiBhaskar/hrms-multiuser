import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth } from "./auth";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Employees from "./pages/Employees";
import Attendance from "./pages/Attendance";
import Leave from "./pages/Leave";
import Reports from "./pages/Reports";
import Departments from "./pages/Departments";
import Announcements from "./pages/Announcements";
import Activity from "./pages/Activity";
import Users from "./pages/Users";
import Profile from "./pages/Profile";

function RequireAuth({ children }) {
  const { user, booting } = useAuth();
  const location = useLocation();

  if (booting) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
        <div className="spinner" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return children;
}

function RequireRole({ check, children }) {
  const { user } = useAuth();
  return check(user) ? children : <Navigate to="/" replace />;
}

export default function App() {
  const { booting } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={booting ? null : <Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="employees" element={<Employees />} />
        <Route path="attendance" element={<Attendance />} />
        <Route path="leave" element={<Leave />} />
        <Route path="departments" element={<Departments />} />
        <Route path="announcements" element={<Announcements />} />
        <Route path="activity" element={<Activity />} />
        <Route path="profile" element={<Profile />} />
        <Route
          path="reports"
          element={
            <RequireRole check={(u) => u?.permissions?.can_manage_people || u?.permissions?.is_manager}>
              <Reports />
            </RequireRole>
          }
        />
        <Route
          path="users"
          element={
            <RequireRole check={(u) => u?.permissions?.is_admin}>
              <Users />
            </RequireRole>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
