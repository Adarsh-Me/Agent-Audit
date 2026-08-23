const Footer = () => {
  return (
    <footer>
      <div className='text-muted-foreground mx-auto flex size-full max-w-360 items-center justify-between gap-3 px-4 py-3 max-sm:flex-col sm:gap-6 sm:px-6'>
        <p className='text-sm text-balance max-sm:text-center'>
          {`©${new Date().getFullYear()}`} AgentAudit — every number carries its confidence interval.
        </p>
      </div>
    </footer>
  )
}

export default Footer
