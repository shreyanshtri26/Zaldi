export default function StockBadge({ quantity }) {
  if (quantity === 0) return <span className="badge bad">Out of stock</span>;
  if (quantity < 10) return <span className="badge warn">Low stock · {quantity}</span>;
  return <span className="badge ok">{quantity} in stock</span>;
}
