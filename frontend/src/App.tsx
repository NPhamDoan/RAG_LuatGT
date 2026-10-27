import { Routes, Route } from "react-router-dom";
import AppLayout from "./components/common/AppLayout";
import RequireAdmin from "./components/common/RequireAdmin";
import ChatPage from "./pages/ChatPage";
import AdminPage from "./pages/AdminPage";
import LoginPage from "./pages/LoginPage";
import { AuthProvider } from "./auth/AuthContext";
import { useChatSessions } from "./hooks/useChatSessions";
import { useDocuments } from "./hooks/useDocuments";

export default function App() {
  const chat = useChatSessions();
  const documentsState = useDocuments();

  // Show badge on nav when jobs are active
  const activeJobs = documentsState.jobs.filter(
    (j) => j.status === "uploading" || j.status === "processing",
  ).length;

  return (
    <AuthProvider>
      <Routes>
        <Route element={<AppLayout activeJobCount={activeJobs} />}>
          <Route index element={<ChatPage chat={chat} />} />
          <Route path="login" element={<LoginPage />} />
          <Route
            path="admin"
            element={
              <RequireAdmin>
                <AdminPage documentsState={documentsState} />
              </RequireAdmin>
            }
          />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
