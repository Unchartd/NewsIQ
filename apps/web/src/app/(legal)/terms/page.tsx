import { permanentRedirect } from "next/navigation";

// /terms is the address most people (and reviewers) try first.
export default function TermsAlias() {
  permanentRedirect("/tos");
}
