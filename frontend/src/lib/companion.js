import { api } from "./api";

/**
 * Post a contextual message to the companion chat and navigate the user there.
 * Uses sessionStorage to mark "just sent" so /companion can scroll to bottom.
 */
export async function sendToCompanion(message, navigate) {
  try {
    await api.post("/companion/chat", { message });
    sessionStorage.setItem("companion_jump", "1");
    navigate("/companion");
  } catch {
    /* main caller should toast */
    throw new Error("companion_send_failed");
  }
}
