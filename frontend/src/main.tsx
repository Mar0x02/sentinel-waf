import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import { App } from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { ConfirmProvider } from "./components/ConfirmProvider";
import { LanguageProvider } from "./i18n/LanguageContext";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <LanguageProvider>
      <AuthProvider>
        <BrowserRouter>
          <ConfirmProvider>
            <App />
            <Toaster
              theme="dark"
              position="bottom-right"
              toastOptions={{
                style: {
                  background: "var(--surface-1)",
                  border: "1px solid var(--border)",
                  color: "var(--text-primary)",
                },
              }}
            />
          </ConfirmProvider>
        </BrowserRouter>
      </AuthProvider>
    </LanguageProvider>
  </React.StrictMode>,
);
