import { useEffect, useState } from "react";
import { fetchApiHealth } from "../services/api.js";

export function useApiHealth() {
  const [health, setHealth] = useState({ status: "checking", details: null });

  useEffect(() => {
    const controller = new AbortController();

    fetchApiHealth(controller.signal)
      .then((details) => setHealth({ status: "connected", details }))
      .catch((error) => {
        if (error.name !== "AbortError") {
          setHealth({ status: "unavailable", details: null });
        }
      });

    return () => controller.abort();
  }, []);

  return health;
}
