// 再訪設計 5章「測るもの」の回数（中身は edge/kazu.mjs）
import { onKazu } from "../../edge/kazu.mjs";
export const onRequest = (context) => onKazu(context);
