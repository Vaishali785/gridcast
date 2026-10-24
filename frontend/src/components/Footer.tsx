import { JSX } from "react"

const Footer = (): JSX.Element => {
	return (
		<footer className="max-w-[1280px] mx-auto px-6 pb-10 text-xs text-muted">
			Source: Elexon BMRS Insights (FUELHH actual, WINDFOR forecast). Accuracy metrics are in MW and
			are not procurement costs or savings — prices and demand are not included.
		</footer>
	)
}

export default Footer
