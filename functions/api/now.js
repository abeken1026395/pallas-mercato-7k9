// 今見ている人数（再訪設計 段階3）。中身は edge/live.mjs
import { onNow } from "../../edge/live.mjs";
export const onRequest = (context) => onNow(context);
