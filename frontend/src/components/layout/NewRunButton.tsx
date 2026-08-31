import { useState } from "react"
import { NewRunDialog } from "@/components/layout/NewRunDialog"
import { Button } from "@/components/ui/Button"
import { Icon } from "@/components/ui/Icon"

export function NewRunButton() {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      <Button variant="primary" onClick={() => setIsOpen(true)}>
        <Icon name="add" className="text-sm" />
        New Run
      </Button>
      {isOpen && <NewRunDialog onClose={() => setIsOpen(false)} />}
    </>
  )
}
