import { Routes, Route } from "react-router"
import AppLayout from "./components/layout/AppLayout"
import MediaManager from "./pages/MediaManager"
import Gallery from "./pages/Gallery"
import SettingsPage from "./pages/SettingsPage"
import Analytics from "./pages/Analytics"
import Batch from "./pages/Batch"
import Schedule from "./pages/Schedule"

function App() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Batch />} />
        <Route path="media" element={<MediaManager />} />
        <Route path="gallery" element={<Gallery />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="batch" element={<Batch />} />
        <Route path="schedule" element={<Schedule />} />
      </Route>
    </Routes>
  )
}

export default App
