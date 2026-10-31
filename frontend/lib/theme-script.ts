/** Shared by the server layout (inline boot script) and the client theme store. No React here. */
export const THEME_STORAGE_KEY = "theme";

/** Runs before first paint (inlined in <head>) so the saved theme never flashes. */
export const THEME_BOOT_SCRIPT = `try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}`;
