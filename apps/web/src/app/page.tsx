import { HeroSearch } from "@/components/HeroSearch";
import { IndexLine } from "@/components/IndexLine";
import { PaintingBackdrop } from "@/components/PaintingBackdrop";

export default function HomePage() {
  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center px-5">
      <PaintingBackdrop variant="home" />
      <div className="br-fade-up relative z-10 w-full max-w-xl">
        <h1 className="mb-3 text-center text-[15px] font-normal tracking-tight text-[var(--muted)]">
          creative fuel for people who build
        </h1>
        <p className="mb-7 text-center text-2xl font-medium leading-snug tracking-tight text-[var(--ink)] sm:text-[28px]">
          Describe an idea.
          <br className="hidden sm:block" /> See the whole landscape to remix.
        </p>
        <HeroSearch />
        <IndexLine />
      </div>
    </main>
  );
}
