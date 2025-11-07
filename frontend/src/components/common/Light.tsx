//src/components/common/Light.tsx
interface LightProps {
    name: string;
    value?: boolean;
    title?: string;
}

export default function Light({ name, value, title }: LightProps) {
    return (
        <div className="flex items-center">
            <div className={`w-6 h-6 rounded-full mr-2 ${value === null || value === undefined ? 'bg-gray-400' : value ? 'bg-green-500' : 'bg-gray-300'}`}
            title={title || (value === null || value === undefined ? 'Desconocido' : value ? 'ON' : 'OFF')}
            ></div>
            <span className="font-bold text-gray-300">
                {value === null || value === undefined ? 'Desconocido' : value ? '' : ''}
            </span>
        </div>
    )
}