// プッシュ通知の登録と解除（再訪設計 段階3）。中身は edge/live.mjs
import { onPush } from "../../edge/live.mjs";
export const onRequest = (context) => onPush(context);
