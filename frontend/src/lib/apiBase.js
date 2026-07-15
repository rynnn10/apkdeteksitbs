/* Updated: Rabu, 15-07-2026 13:10 WIB | v2.5.0 */
// ponytail: single source of truth for server base URL — Riwayat/Dashboard/DeteksiBaru
// all read the same saved IP instead of each guessing "/api" (which never resolves
// from the APK's file:// origin).
export function getApiBase() {
  const ip = localStorage.getItem("server_ip");
  return ip ? `http://${ip}:8000` : "";
}
