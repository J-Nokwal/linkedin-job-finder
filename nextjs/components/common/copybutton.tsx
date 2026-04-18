'use client'
import { Button } from "../ui/button"

const CopyButton = ({text}: {text: string}) => {
    function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text);
}
    return (
        <Button
      variant="outline"
      size="sm"
      onClick={() => copyToClipboard(text)}
    >
      Copy
    </Button>
    )
}

export default CopyButton