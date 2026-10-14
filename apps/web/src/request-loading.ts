let pending = 0;
const listeners = new Set<() => void>();
export const pendingRequests = () => pending;
export const subscribeRequests = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};
export function beginRequest() {
  pending++;
  listeners.forEach((listener) => listener());
  let finished = false;
  return () => {
    if (finished) return;
    finished = true;
    pending--;
    listeners.forEach((listener) => listener());
  };
}
