import { Routes, Route } from "react-router-dom"
import AppLayout from "./components/layout/AppLayout"
import MediaManager from "./pages/MediaManager"
import Presets from "./pages/Presets"
import Gallery from "./pages/Gallery"
import SettingsPage from "./pages/SettingsPage"
import Batch from "./pages/Batch"

function App() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Batch />} />
        <Route path="media" element={<MediaManager />} />
        <Route path="presets" element={<Presets />} />
        <Route path="gallery" element={<Gallery />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="batch" element={<Batch />} />
      </Route>
    </Routes>
  )
}

export default App
