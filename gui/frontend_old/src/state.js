/**
 * Centralized application state and event bus.
 * All modules read/write from this shared state object.
 * The event bus (on/emit) enables decoupled communication.
 */

const listeners = {};

/**
 * Subscribe to an event.
 * @param {string} event - Event name.
 * @param {Function} callback - Handler invoked with event data.
 */
export function on(event, callback) {
  if (!listeners[event]) {
    listeners[event] = [];
  }
  listeners[event].push(callback);
}

/**
 * Emit an event to all registered listeners.
 * @param {string} event - Event name.
 * @param {*} data - Data passed to each listener.
 */
export function emit(event, data) {
  if (listeners[event]) {
    for (const cb of listeners[event]) {
      try {
        cb(data);
      } catch (err) {
        console.error(`[EventBus] Error in listener for "${event}":`, err);
      }
    }
  }
}

/**
 * Global application state.
 * Modules import and mutate this directly, then emit events to notify the UI.
 */
export const state = {
  /** Current app / project state from the backend. */
  app: {},

  /** User settings (paths, defaults, etc.). */
  settings: {},

  /** Saved presets keyed by name. */
  presets: {},

  /** Available TTS voices – array of {name, value}. */
  voices: [],

  /** Which asset-selector target is currently active (e.g. 'background_video'). */
  activeSelectorTarget: '',

  /** Interval ID used when polling compilation status. */
  compilationPollInterval: null,

  /** Whether the sidebar is collapsed. */
  sidebarCollapsed: false,
};
