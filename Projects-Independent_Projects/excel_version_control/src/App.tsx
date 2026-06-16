import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './lib/auth';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import SpreadsheetView from './pages/SpreadsheetView';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
    const { user, loading } = useAuth();

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            </div>
        );
    }

    if (!user) return <Navigate to="/login" />;
    return <>{children}</>;
}

function App() {
    return (
        <AuthProvider>
            <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                <Route path="/spreadsheet/:id" element={<ProtectedRoute><SpreadsheetView /></ProtectedRoute>} />
            </Routes>
        </AuthProvider>
    );
}

export default App;
